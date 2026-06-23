"""
GraphCodeBERT + DFG_cpp encoder.

Реализует логику из microsoft/CodeBERT model.py / run.py,
адаптированную для C++ через DFG_cpp.

Формат входа:
  X = [CLS, c1…cn, SEP, v1…vm, PAD…]
  position_ids: code_tokens → i+2, dfg_nodes → 0, pad → 1
  attention_mask (2D, graph-guided):
    - code↔code: всё видит всё
    - CLS/SEP: видят весь non-pad контекст
    - dfg_node ↔ code_tokens: только те, с которыми связан по графу
    - dfg_node ↔ dfg_node: только соседи по рёбрам DFG
"""

import sys, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["HF_HOME"] = "Q:\\hf_cache"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
import tree_sitter_cpp as tscpp
from tree_sitter import Language, Parser

from dfg_utils import tree_to_token_index, index_to_code_token
from DFG_cpp import DFG_cpp

# ── парсер ──────────────────────────────────────────────────────────────────
CPP_LANG = Language(tscpp.language())
_parser = Parser(CPP_LANG)

# ── константы ───────────────────────────────────────────────────────────────
CODE_LENGTH      = 256   # max BPE токенов кода (без CLS/SEP)
DFG_LENGTH       = 64    # max DFG-узлов
TOTAL_LENGTH     = CODE_LENGTH + DFG_LENGTH   # 320


# ============================================================================
# Шаг 1: парсинг C++ → (raw_tokens, dfg)
# ============================================================================

def _extract_tokens_and_dfg(code: str):
    """tree-sitter-cpp → raw token strings + отфильтрованный DFG."""
    code_lines = code.split('\n')
    tree = _parser.parse(code.encode())
    root = tree.root_node

    tokens_index = tree_to_token_index(root)
    raw_tokens = [index_to_code_token(idx, code_lines) for idx in tokens_index]

    index_to_code = {idx: (i, tok) for i, (idx, tok) in
                     enumerate(zip(tokens_index, raw_tokens))}

    try:
        dfg, _ = DFG_cpp(root, index_to_code, {})
    except Exception:
        dfg = []

    dfg = sorted(dfg, key=lambda x: x[1])

    # оставляем только узлы, участвующие в хотя бы одном ребре
    active = set()
    for d in dfg:
        if d[-1]:           # есть исходящие рёбра (src_idxs)
            active.add(d[1])
        for src in d[-1]:
            active.add(src)
    dfg = [d for d in dfg if d[1] in active]

    return raw_tokens, dfg


# ============================================================================
# Шаг 2: BPE-токенизация + ori2cur_pos
# ============================================================================

def _bpe_tokenize(raw_tokens, tokenizer):
    """
    Каждый raw token токенизируем через '@ x' трюк (как в оригинале),
    чтобы получить subword-токены без артефактов пробела на первом токене.
    Возвращает список списков и словарь ori2cur_pos.
    """
    bpe_groups = []
    for i, tok in enumerate(raw_tokens):
        if i == 0:
            sub = tokenizer.tokenize(tok)
        else:
            sub = tokenizer.tokenize('@ ' + tok)[1:]  # убираем '@'
        bpe_groups.append(sub if sub else [tokenizer.unk_token])

    ori2cur_pos = {-1: (0, 0)}
    for i, group in enumerate(bpe_groups):
        prev_end = ori2cur_pos[i - 1][1]
        ori2cur_pos[i] = (prev_end, prev_end + len(group))

    flat_bpe = [tok for group in bpe_groups for tok in group]
    return flat_bpe, ori2cur_pos


# ============================================================================
# Шаг 3: сборка полного входа модели
# ============================================================================

def build_model_input(cpp_code: str, tokenizer):
    """
    Возвращает dict с:
      input_ids       : (1, TOTAL_LENGTH)   LongTensor
      attention_mask  : (1, TOTAL_LENGTH, TOTAL_LENGTH)  BoolTensor
      position_ids    : (1, TOTAL_LENGTH)   LongTensor
    """
    raw_tokens, dfg = _extract_tokens_and_dfg(cpp_code)
    flat_bpe, ori2cur_pos = _bpe_tokenize(raw_tokens, tokenizer)

    # --- усечение --------------------------------------------------------
    max_code_bpe = CODE_LENGTH + DFG_LENGTH - 3 - min(len(dfg), DFG_LENGTH)
    max_code_bpe = min(max_code_bpe, 512 - 3)
    flat_bpe = flat_bpe[:max_code_bpe]

    source_tokens = [tokenizer.cls_token] + flat_bpe + [tokenizer.sep_token]
    source_ids    = tokenizer.convert_tokens_to_ids(source_tokens)
    # position: code tokens → i+pad_id+1 = i+2 (pad_token_id=1 для RoBERTa)
    position_idx  = [i + tokenizer.pad_token_id + 1
                     for i in range(len(source_tokens))]

    dfg = dfg[:TOTAL_LENGTH - len(source_tokens)]

    # DFG-узлы добавляются как unk_token (имя переменной игнорируется моделью —
    # embedding заменяется усреднённым embedding code-токенов в forward())
    source_tokens += [x[0] for x in dfg]
    source_ids    += [tokenizer.unk_token_id] * len(dfg)
    position_idx  += [0] * len(dfg)

    padding_length = TOTAL_LENGTH - len(source_ids)
    source_ids   += [tokenizer.pad_token_id] * padding_length
    position_idx += [tokenizer.pad_token_id] * padding_length

    # --- reindex DFG -----------------------------------------------------
    # reverse_index: оригинальный token_idx → слот в dfg-массиве
    reverse_index = {x[1]: i for i, x in enumerate(dfg)}
    for i, x in enumerate(dfg):
        dfg[i] = x[:-1] + ([reverse_index[s] for s in x[-1]
                             if s in reverse_index],)

    dfg_to_dfg  = [x[-1] for x in dfg]
    # ori2cur_pos[x[1]] → (start, end) в плоском BPE; смещаем на 1 (CLS)
    cls_offset  = len([tokenizer.cls_token])  # = 1
    dfg_to_code = []
    for x in dfg:
        raw_idx = x[1]
        if raw_idx in ori2cur_pos:
            a, b = ori2cur_pos[raw_idx]
        else:
            a, b = 0, 0
        dfg_to_code.append((a + cls_offset, b + cls_offset))

    # --- 2D attention mask -----------------------------------------------
    attn = np.zeros((TOTAL_LENGTH, TOTAL_LENGTH), dtype=bool)

    node_index = sum(i > 1 for i in position_idx)      # конец code-сегмента
    max_len    = sum(i != 1 for i in position_idx)      # code + dfg (без pad)

    # 1. code tokens видят друг друга
    attn[:node_index, :node_index] = True

    # 2. CLS (id=0) и SEP (id=2) видят весь non-pad контекст
    for idx, tid in enumerate(source_ids):
        if tid in (tokenizer.cls_token_id, tokenizer.sep_token_id):
            attn[idx, :max_len] = True

    # 3. DFG-узлы ↔ code tokens (bidirectional)
    for i, (a, b) in enumerate(dfg_to_code):
        pos = i + node_index
        if pos < TOTAL_LENGTH and a < node_index and b <= node_index:
            attn[pos, a:b] = True
            attn[a:b, pos] = True

    # 4. DFG-узлы ↔ соседние DFG-узлы
    for i, neighbors in enumerate(dfg_to_dfg):
        pos = i + node_index
        if pos >= TOTAL_LENGTH:
            continue
        for nb in neighbors:
            nb_pos = nb + node_index
            if nb_pos < TOTAL_LENGTH:
                attn[pos, nb_pos] = True

    return {
        "input_ids":      torch.tensor(source_ids,    dtype=torch.long).unsqueeze(0),
        "attention_mask": torch.from_numpy(attn).unsqueeze(0),   # (1,320,320) bool
        "position_ids":   torch.tensor(position_idx,  dtype=torch.long).unsqueeze(0),
        # сохраняем для forward-pass
        "_position_idx":  position_idx,
        "_n_dfg":         len(dfg),
        "_node_index":    node_index,
    }


# ============================================================================
# Шаг 4: forward с заменой DFG-embeddings (как в model.py Microsoft)
# ============================================================================

def get_embedding_with_dfg(cpp_code: str, model, tokenizer,
                            device: torch.device) -> np.ndarray:
    """
    Прогоняет C++ код через GraphCodeBERT с graph-guided attention.
    Возвращает mean-pooled эмбеддинг (только по code-токенам).
    """
    inp = build_model_input(cpp_code, tokenizer)
    node_index = inp["_node_index"]

    input_ids   = inp["input_ids"].to(device)          # (1, 320)
    attn_mask   = inp["attention_mask"].to(device)      # (1, 320, 320) bool
    position_ids = inp["position_ids"].to(device)       # (1, 320)

    # position_idx маски: nodes_mask = position==0 (DFG), token_mask = position>=2 (code)
    nodes_mask = position_ids.eq(0)                     # (1, 320)
    token_mask = position_ids.ge(2)                     # (1, 320)

    with torch.no_grad():
        # 1. получаем word embeddings
        word_emb = model.embeddings.word_embeddings(input_ids)   # (1,320,768)

        # 2. заменяем DFG-embedding на avg code-token embeddings
        #    nodes_to_token_mask: (1,320,320) — для каждого DFG-узла i
        #    какие code-токены j он видит в attn_mask
        n2t = (nodes_mask[:, :, None]          # (1,320,1)
               & token_mask[:, None, :]        # (1,1,320)
               & attn_mask)                    # (1,320,320)
        n2t = n2t.float()
        denom = n2t.sum(-1, keepdim=True) + 1e-10
        n2t = n2t / denom                      # нормировка по code-токенам

        avg_emb = torch.bmm(n2t, word_emb)     # (1,320,768)

        # DFG-узлы получают avg_emb, code-токены остаются как есть
        inputs_embeds = (word_emb * (~nodes_mask[:, :, None]).float()
                         + avg_emb * nodes_mask[:, :, None].float())

        # 3. прогоняем через encoder
        # attention_mask: передаём как (1, 320, 320); transformers обработает
        # как 3D → (1, 1, 320, 320)
        attn_float = attn_mask.float()   # HuggingFace ждёт float для 3D масок

        outputs = model(
            inputs_embeds=inputs_embeds,
            attention_mask=attn_float,
            position_ids=position_ids,
            token_type_ids=position_ids.eq(-1).long(),  # все нули
        )
        last_hidden = outputs.last_hidden_state   # (1, 320, 768)

        # 4. mean pooling только по code-токенам (position >= 2)
        code_mask = token_mask.unsqueeze(-1).float()   # (1, 320, 1)
        emb = (last_hidden * code_mask).sum(1) / (code_mask.sum(1) + 1e-10)
        emb = F.normalize(emb, dim=-1)

    return emb.cpu().numpy()[0]


# ============================================================================
# Шаг 5: token-only baseline (без DFG)
# ============================================================================

def get_embedding_no_dfg(cpp_code: str, model, tokenizer,
                          device: torch.device) -> np.ndarray:
    """Простой режим без DFG — для сравнения."""
    inputs = tokenizer(cpp_code, return_tensors="pt",
                       truncation=True, max_length=512, padding=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        out = model(**inputs)
        mask = inputs["attention_mask"].unsqueeze(-1).float()
        emb = (out.last_hidden_state * mask).sum(1) / mask.sum(1)
        emb = F.normalize(emb, dim=-1)
    return emb.cpu().numpy()[0]
