# AI Model — GraphCodeBERT + DFG для C++

Модуль Encoder для системы антиплагиата кода на C++.  
Использует модель [microsoft/graphcodebert-base](https://huggingface.co/microsoft/graphcodebert-base)
с кастомным DFG-парсером для C++.

## Структура

```
ai_model/
├── DFG_cpp.py                  # DFG-парсер для C++ (адаптирован из DFG_java Microsoft)
├── dfg_utils.py                # Утилиты: токенизация AST, построение индексов
├── graphcodebert_dfg_encoder.py # Encoder: build_model_input(), get_embedding_with_dfg()
├── baseline_eval.py            # Оценка baseline на POJ-104
└── requirements.txt
```

## Установка

```bash
# PyTorch с CUDA (рекомендуется, GTX 1660 / CUDA 11.8)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# Остальные зависимости
pip install -r requirements.txt
```

## Быстрый старт

```python
import torch
from transformers import AutoTokenizer, AutoModel
from graphcodebert_dfg_encoder import get_embedding_with_dfg

device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tokenizer = AutoTokenizer.from_pretrained("microsoft/graphcodebert-base")
model     = AutoModel.from_pretrained("microsoft/graphcodebert-base").to(device).eval()

code = """
int add(int a, int b) {
    return a + b;
}
"""
embedding = get_embedding_with_dfg(code, model, tokenizer, device)
# → numpy array shape (768,)
```

## Оценка baseline на POJ-104

```bash
python baseline_eval.py --programs 400 --pairs 800 --seed 42
```

Сохраняет в `baseline_results/`:
- `pairs.csv` — список пар (id_a, id_b, label) для тестирования любым алгоритмом
- `programs.csv` — список программ (id, label, code)
- `sims_dfg.npy`, `sims_ndfg.npy`, `labels.npy` — результаты для сравнения
- `metrics.csv` — ROC-AUC, F1, Precision, Recall, Accuracy
- `baseline_plots.png` — ROC-кривые и гистограммы сходства

### Baseline результаты (zero-shot, без fine-tuning)

| Метрика   | Без DFG | С DFG  | Δ      |
|-----------|---------|--------|--------|
| ROC-AUC   | 0.5828  | 0.7783 | +0.195 |
| F1        | 0.4268  | 0.6812 | +0.254 |
| Precision | 0.7712  | 0.8153 | +0.044 |
| Recall    | 0.2950  | 0.5850 | +0.290 |
| Accuracy  | 0.6038  | 0.7262 | +0.123 |

## Использование `pairs.csv` для классических алгоритмов

Файл `pairs.csv` содержит те же пары программ (с метками clone/non-clone),
на которых оценивался DFG+GraphCodeBERT. Это позволяет напрямую сравнить
классические алгоритмы антиплагиата с нейросетевым подходом на одних данных.

```python
import pandas as pd

pairs    = pd.read_csv("baseline_results/pairs.csv")
programs = pd.read_csv("baseline_results/programs.csv")
code_map = dict(zip(programs["id"], programs["code"]))

for _, row in pairs.iterrows():
    code_a = code_map[row["id_a"]]
    code_b = code_map[row["id_b"]]
    label  = row["label"]   # 1 = clone, 0 = non-clone
    # ... ваш алгоритм ...
```

## Формат входа модели

Следует формату оригинального Microsoft GraphCodeBERT:

```
X = [CLS, c1…cn, SEP, v1…vm, PAD…]
```

- `c1…cn` — BPE-токены кода
- `v1…vm` — переменные из DFG-графа (как `<unk>`, embedding заменяется средним по связанным токенам)
- `position_ids`: код → `i+2`, DFG-узлы → `0`, padding → `1`
- `attention_mask` (2D, graph-guided): code↔code полная связность, DFG↔code только по рёбрам графа

## DFG для C++

`DFG_cpp.py` покрывает:
- Объявления с инициализацией (`int x = a + b`)
- Присваивания включая `+=`, `-=`, `*=`, `/=`
- `i++`, `--j` (update_expression)
- `if / else if / else`
- `for` и `while` циклы (включая вложенные)
- Указатели и ссылки (`int* p`, `int& ref`)
- Массивы и индексация (`arr[i]`)
- Тернарный оператор
- Рекурсивные функции
- Вызовы функций с аргументами
