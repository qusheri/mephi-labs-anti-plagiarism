#include "antiplag/algos/detectors.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <numeric>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <utility>

namespace antiplag::algos {
namespace {

struct IndexedHash {
    std::uint64_t hash = 0;
    std::size_t position = 0;
};

struct Tile {
    std::size_t a = 0;
    std::size_t b = 0;
    std::size_t length = 0;
};

std::uint64_t fnv1a_mix(std::uint64_t value, std::string_view text) {
    constexpr std::uint64_t prime = 1099511628211ull;
    for (unsigned char c : text) {
        value ^= c;
        value *= prime;
    }
    value ^= 0xff;
    value *= prime;
    return value;
}

std::uint64_t hash_tokens(
    const std::vector<std::string>& values,
    std::size_t start,
    std::size_t length) {
    std::uint64_t value = 1469598103934665603ull;
    for (std::size_t i = 0; i < length; ++i) {
        value = fnv1a_mix(value, values[start + i]);
    }
    return value;
}

std::vector<IndexedHash> kgram_hashes(
    const std::vector<std::string>& values,
    std::size_t k) {
    std::vector<IndexedHash> hashes;
    if (k == 0 || values.size() < k) {
        return hashes;
    }

    hashes.reserve(values.size() - k + 1);
    for (std::size_t i = 0; i + k <= values.size(); ++i) {
        hashes.push_back({hash_tokens(values, i, k), i});
    }
    return hashes;
}

std::unordered_map<std::uint64_t, std::vector<std::size_t>> positions_by_hash(
    const std::vector<IndexedHash>& hashes) {
    std::unordered_map<std::uint64_t, std::vector<std::size_t>> positions;
    for (const auto& item : hashes) {
        positions[item.hash].push_back(item.position);
    }
    return positions;
}

std::unordered_set<std::uint64_t> hash_set(const std::vector<IndexedHash>& hashes) {
    std::unordered_set<std::uint64_t> values;
    values.reserve(hashes.size());
    for (const auto& item : hashes) {
        values.insert(item.hash);
    }
    return values;
}

std::size_t intersection_size(
    const std::unordered_set<std::uint64_t>& a,
    const std::unordered_set<std::uint64_t>& b) {
    const auto* small = &a;
    const auto* large = &b;
    if (small->size() > large->size()) {
        std::swap(small, large);
    }

    std::size_t count = 0;
    for (auto value : *small) {
        if (large->find(value) != large->end()) {
            ++count;
        }
    }
    return count;
}

double jaccard(
    const std::unordered_set<std::uint64_t>& a,
    const std::unordered_set<std::uint64_t>& b) {
    if (a.empty() || b.empty()) {
        return 0.0;
    }
    const std::size_t inter = intersection_size(a, b);
    const std::size_t uni = a.size() + b.size() - inter;
    return uni == 0 ? 0.0 : static_cast<double>(inter) / static_cast<double>(uni);
}

double containment(
    const std::unordered_set<std::uint64_t>& a,
    const std::unordered_set<std::uint64_t>& b) {
    if (a.empty() || b.empty()) {
        return 0.0;
    }
    const std::size_t inter = intersection_size(a, b);
    return static_cast<double>(inter) / static_cast<double>(std::min(a.size(), b.size()));
}

std::string size_param(std::size_t value) {
    return std::to_string(value);
}

MatchFragment make_fragment(
    const std::vector<Token>& a_tokens,
    const std::vector<Token>& b_tokens,
    std::size_t a_start,
    std::size_t b_start,
    std::size_t length,
    std::string explanation) {
    const std::size_t a_last = std::min(a_start + length - 1, a_tokens.size() - 1);
    const std::size_t b_last = std::min(b_start + length - 1, b_tokens.size() - 1);

    MatchFragment fragment;
    fragment.file_a_token_start = a_start;
    fragment.file_a_token_end = a_last + 1;
    fragment.file_b_token_start = b_start;
    fragment.file_b_token_end = b_last + 1;
    fragment.file_a_line_start = a_tokens[a_start].span.line_start;
    fragment.file_a_line_end = a_tokens[a_last].span.line_end;
    fragment.file_b_line_start = b_tokens[b_start].span.line_start;
    fragment.file_b_line_end = b_tokens[b_last].span.line_end;
    fragment.explanation = std::move(explanation);
    return fragment;
}

std::unordered_set<std::uint64_t> common_hashes(
    const std::unordered_set<std::uint64_t>& a,
    const std::unordered_set<std::uint64_t>& b) {
    std::unordered_set<std::uint64_t> common;
    const auto* small = &a;
    const auto* large = &b;
    if (small->size() > large->size()) {
        std::swap(small, large);
    }

    for (auto value : *small) {
        if (large->find(value) != large->end()) {
            common.insert(value);
        }
    }
    return common;
}

std::vector<MatchFragment> fragments_from_common_hashes(
    const std::vector<Token>& a_tokens,
    const std::vector<Token>& b_tokens,
    const std::unordered_map<std::uint64_t, std::vector<std::size_t>>& a_positions,
    const std::unordered_map<std::uint64_t, std::vector<std::size_t>>& b_positions,
    const std::unordered_set<std::uint64_t>& common,
    std::size_t length,
    std::size_t max_fragments,
    std::string_view explanation) {
    std::vector<MatchFragment> fragments;
    if (a_tokens.empty() || b_tokens.empty() || length == 0) {
        return fragments;
    }

    for (auto hash : common) {
        auto a_it = a_positions.find(hash);
        auto b_it = b_positions.find(hash);
        if (a_it == a_positions.end() || b_it == b_positions.end()) {
            continue;
        }
        fragments.push_back(make_fragment(
            a_tokens,
            b_tokens,
            a_it->second.front(),
            b_it->second.front(),
            length,
            std::string(explanation)));
        if (fragments.size() >= max_fragments) {
            break;
        }
    }

    std::sort(fragments.begin(), fragments.end(), [](const auto& lhs, const auto& rhs) {
        return std::tie(lhs.file_a_line_start, lhs.file_b_line_start)
            < std::tie(rhs.file_a_line_start, rhs.file_b_line_start);
    });
    return fragments;
}

std::vector<IndexedHash> winnow(
    const std::vector<IndexedHash>& hashes,
    std::size_t window) {
    std::vector<IndexedHash> fingerprints;
    if (hashes.empty() || window == 0) {
        return fingerprints;
    }
    if (hashes.size() <= window) {
        auto best = std::min_element(hashes.begin(), hashes.end(), [](const auto& lhs, const auto& rhs) {
            if (lhs.hash != rhs.hash) {
                return lhs.hash < rhs.hash;
            }
            return lhs.position > rhs.position;
        });
        fingerprints.push_back(*best);
        return fingerprints;
    }

    std::size_t last_selected = std::numeric_limits<std::size_t>::max();
    for (std::size_t start = 0; start + window <= hashes.size(); ++start) {
        std::size_t best = start;
        for (std::size_t offset = 1; offset < window; ++offset) {
            const std::size_t candidate = start + offset;
            if (hashes[candidate].hash < hashes[best].hash
                || (hashes[candidate].hash == hashes[best].hash
                    && hashes[candidate].position > hashes[best].position)) {
                best = candidate;
            }
        }
        if (hashes[best].position != last_selected) {
            fingerprints.push_back(hashes[best]);
            last_selected = hashes[best].position;
        }
    }
    return fingerprints;
}

bool range_is_free(const std::vector<bool>& marked, std::size_t start, std::size_t length) {
    for (std::size_t i = 0; i < length; ++i) {
        if (marked[start + i]) {
            return false;
        }
    }
    return true;
}

void mark_range(std::vector<bool>& marked, std::size_t start, std::size_t length) {
    for (std::size_t i = 0; i < length; ++i) {
        marked[start + i] = true;
    }
}

std::vector<Tile> greedy_tiles(
    const std::vector<std::string>& a,
    const std::vector<std::string>& b,
    std::size_t min_match_length) {
    std::vector<Tile> tiles;
    if (a.empty() || b.empty() || min_match_length == 0) {
        return tiles;
    }

    std::unordered_map<std::string, std::vector<std::size_t>> b_positions;
    for (std::size_t j = 0; j < b.size(); ++j) {
        b_positions[b[j]].push_back(j);
    }

    std::vector<bool> marked_a(a.size(), false);
    std::vector<bool> marked_b(b.size(), false);

    while (true) {
        std::size_t best_length = min_match_length;
        std::vector<Tile> matches;

        for (std::size_t i = 0; i < a.size(); ++i) {
            if (marked_a[i]) {
                continue;
            }
            auto it = b_positions.find(a[i]);
            if (it == b_positions.end()) {
                continue;
            }

            for (std::size_t j : it->second) {
                if (marked_b[j]) {
                    continue;
                }

                std::size_t length = 0;
                while (i + length < a.size()
                    && j + length < b.size()
                    && !marked_a[i + length]
                    && !marked_b[j + length]
                    && a[i + length] == b[j + length]) {
                    ++length;
                }

                if (length >= best_length) {
                    if (length > best_length) {
                        matches.clear();
                        best_length = length;
                    }
                    matches.push_back({i, j, length});
                }
            }
        }

        if (matches.empty()) {
            break;
        }

        std::sort(matches.begin(), matches.end(), [](const auto& lhs, const auto& rhs) {
            if (lhs.length != rhs.length) {
                return lhs.length > rhs.length;
            }
            return std::tie(lhs.a, lhs.b) < std::tie(rhs.a, rhs.b);
        });

        bool added = false;
        for (const auto& match : matches) {
            if (!range_is_free(marked_a, match.a, match.length)
                || !range_is_free(marked_b, match.b, match.length)) {
                continue;
            }
            mark_range(marked_a, match.a, match.length);
            mark_range(marked_b, match.b, match.length);
            tiles.push_back(match);
            added = true;
        }

        if (!added) {
            break;
        }
    }

    std::sort(tiles.begin(), tiles.end(), [](const auto& lhs, const auto& rhs) {
        return std::tie(lhs.a, lhs.b) < std::tie(rhs.a, rhs.b);
    });
    return tiles;
}

bool is_loop_keyword(std::string_view value) {
    return value == "for" || value == "while" || value == "do";
}

bool is_branch_keyword(std::string_view value) {
    return value == "if" || value == "else" || value == "switch" || value == "case"
        || value == "default" || value == "match" || value == "elif";
}

bool is_decl_keyword(std::string_view value) {
    return value == "class" || value == "struct" || value == "interface" || value == "enum"
        || value == "def" || value == "function" || value == "template" || value == "namespace";
}

bool is_type_keyword(std::string_view value) {
    return value == "int" || value == "long" || value == "short" || value == "float"
        || value == "double" || value == "char" || value == "bool" || value == "void"
        || value == "auto" || value == "var" || value == "let" || value == "const";
}

bool is_assignment(std::string_view value) {
    return value == "=" || value == "+=" || value == "-=" || value == "*=" || value == "/="
        || value == "%=" || value == "<<=" || value == ">>=";
}

bool is_comparison(std::string_view value) {
    return value == "==" || value == "!=" || value == "<" || value == ">" || value == "<="
        || value == ">=" || value == "===" || value == "!==";
}

std::string operator_role(std::string_view value) {
    if (is_assignment(value)) {
        return "OP_ASSIGN";
    }
    if (is_comparison(value)) {
        return "OP_COMPARE";
    }
    if (value == "&&" || value == "||" || value == "and" || value == "or" || value == "!") {
        return "OP_LOGIC";
    }
    if (value == "+" || value == "-" || value == "*" || value == "/" || value == "%"
        || value == "**") {
        return "OP_ARITH";
    }
    return "OP";
}

std::vector<std::string> structural_skeleton(const std::vector<Token>& tokens) {
    std::vector<std::string> skeleton;
    skeleton.reserve(tokens.size());

    for (std::size_t i = 0; i < tokens.size(); ++i) {
        const auto& token = tokens[i];
        const std::string& value = token.normalized;

        if (token.kind == TokenKind::Keyword) {
            if (is_loop_keyword(value)) {
                skeleton.push_back("LOOP");
            } else if (is_branch_keyword(value)) {
                skeleton.push_back("BRANCH");
            } else if (is_decl_keyword(value)) {
                skeleton.push_back("DECL");
            } else if (is_type_keyword(value)) {
                skeleton.push_back("TYPE");
            } else if (value == "return" || value == "yield") {
                skeleton.push_back("RETURN");
            } else if (value == "break" || value == "continue") {
                skeleton.push_back("JUMP");
            } else if (value == "try" || value == "catch" || value == "except" || value == "finally") {
                skeleton.push_back("EXCEPTION");
            } else {
                skeleton.push_back("KW");
            }
            continue;
        }

        if (token.kind == TokenKind::Identifier) {
            const bool looks_like_call = i + 1 < tokens.size() && tokens[i + 1].text == "(";
            skeleton.push_back(looks_like_call ? "CALL" : "ID");
            continue;
        }

        if (token.kind == TokenKind::Number || token.kind == TokenKind::String) {
            skeleton.push_back("LITERAL");
            continue;
        }

        if (token.kind == TokenKind::Operator) {
            skeleton.push_back(operator_role(value));
            continue;
        }

        if (token.kind == TokenKind::Separator) {
            if (value == "{" || value == "}" || value == "(" || value == ")" || value == "["
                || value == "]") {
                skeleton.push_back("GROUP_" + value);
            } else if (value == ";" || value == ":") {
                skeleton.push_back("STMT_END");
            }
        }
    }

    return skeleton;
}

std::unordered_map<std::string, double> feature_counts(const std::vector<std::string>& skeleton) {
    std::unordered_map<std::string, double> counts;
    int nesting = 0;
    int max_nesting = 0;

    for (const auto& item : skeleton) {
        counts[item] += 1.0;
        if (item == "GROUP_{" || item == "GROUP_(" || item == "GROUP_[") {
            ++nesting;
            max_nesting = std::max(max_nesting, nesting);
        } else if (item == "GROUP_}" || item == "GROUP_)" || item == "GROUP_]") {
            nesting = std::max(0, nesting - 1);
        }
    }

    counts["MAX_NESTING"] = static_cast<double>(max_nesting);
    counts["TOTAL"] = static_cast<double>(skeleton.size());
    return counts;
}

double cosine_similarity(
    const std::unordered_map<std::string, double>& a,
    const std::unordered_map<std::string, double>& b) {
    double dot = 0.0;
    double norm_a = 0.0;
    double norm_b = 0.0;

    for (const auto& [key, value] : a) {
        norm_a += value * value;
        auto it = b.find(key);
        if (it != b.end()) {
            dot += value * it->second;
        }
    }
    for (const auto& item : b) {
        norm_b += item.second * item.second;
    }

    if (norm_a == 0.0 || norm_b == 0.0) {
        return 0.0;
    }
    return dot / (std::sqrt(norm_a) * std::sqrt(norm_b));
}

double clamp_score(double value) {
    if (value < 0.0) {
        return 0.0;
    }
    if (value > 1.0) {
        return 1.0;
    }
    return value;
}

DetectionResult empty_result(std::string algorithm) {
    DetectionResult result;
    result.algorithm = std::move(algorithm);
    result.score = 0.0;
    result.containment = 0.0;
    result.warnings.push_back("not enough tokens to compare");
    return result;
}

}  // namespace

DetectionResult compare_ngrams(
    std::string_view code_a,
    std::string_view code_b,
    const NGramOptions& options) {
    auto a_tokens = tokenize(code_a, options.tokenizer);
    auto b_tokens = tokenize(code_b, options.tokenizer);
    auto a_values = normalized_values(a_tokens);
    auto b_values = normalized_values(b_tokens);

    DetectionResult result;
    result.algorithm = "token_ngram";
    result.parameters["k"] = size_param(options.k);

    auto a_hashes = kgram_hashes(a_values, options.k);
    auto b_hashes = kgram_hashes(b_values, options.k);
    if (a_hashes.empty() || b_hashes.empty()) {
        return empty_result(result.algorithm);
    }

    auto a_set = hash_set(a_hashes);
    auto b_set = hash_set(b_hashes);
    result.score = jaccard(a_set, b_set);
    result.containment = containment(a_set, b_set);

    auto common = common_hashes(a_set, b_set);
    result.fragments = fragments_from_common_hashes(
        a_tokens,
        b_tokens,
        positions_by_hash(a_hashes),
        positions_by_hash(b_hashes),
        common,
        options.k,
        20,
        "shared normalized token k-gram");
    return result;
}

DetectionResult compare_winnowing(
    std::string_view code_a,
    std::string_view code_b,
    const WinnowingOptions& options) {
    auto a_tokens = tokenize(code_a, options.tokenizer);
    auto b_tokens = tokenize(code_b, options.tokenizer);
    auto a_values = normalized_values(a_tokens);
    auto b_values = normalized_values(b_tokens);

    DetectionResult result;
    result.algorithm = "winnowing";
    result.parameters["k"] = size_param(options.k);
    result.parameters["window"] = size_param(options.window);

    auto a_fingerprints = winnow(kgram_hashes(a_values, options.k), options.window);
    auto b_fingerprints = winnow(kgram_hashes(b_values, options.k), options.window);
    if (a_fingerprints.empty() || b_fingerprints.empty()) {
        return empty_result(result.algorithm);
    }

    auto a_set = hash_set(a_fingerprints);
    auto b_set = hash_set(b_fingerprints);
    result.score = jaccard(a_set, b_set);
    result.containment = containment(a_set, b_set);

    auto common = common_hashes(a_set, b_set);
    result.fragments = fragments_from_common_hashes(
        a_tokens,
        b_tokens,
        positions_by_hash(a_fingerprints),
        positions_by_hash(b_fingerprints),
        common,
        options.k,
        20,
        "shared winnowing fingerprint");
    return result;
}

DetectionResult compare_greedy_string_tiling(
    std::string_view code_a,
    std::string_view code_b,
    const GreedyStringTilingOptions& options) {
    auto a_tokens = tokenize(code_a, options.tokenizer);
    auto b_tokens = tokenize(code_b, options.tokenizer);
    auto a_values = normalized_values(a_tokens);
    auto b_values = normalized_values(b_tokens);

    DetectionResult result;
    result.algorithm = "greedy_string_tiling";
    result.parameters["min_match_length"] = size_param(options.min_match_length);

    auto tiles = greedy_tiles(a_values, b_values, options.min_match_length);
    if (tiles.empty()) {
        result.score = 0.0;
        result.containment = 0.0;
        return result;
    }

    const std::size_t covered = std::accumulate(
        tiles.begin(),
        tiles.end(),
        std::size_t{0},
        [](std::size_t total, const Tile& tile) { return total + tile.length; });

    result.score = (2.0 * static_cast<double>(covered))
        / static_cast<double>(a_values.size() + b_values.size());
    result.containment = static_cast<double>(covered)
        / static_cast<double>(std::min(a_values.size(), b_values.size()));

    for (const auto& tile : tiles) {
        result.fragments.push_back(make_fragment(
            a_tokens,
            b_tokens,
            tile.a,
            tile.b,
            tile.length,
            "non-overlapping normalized token tile"));
        if (result.fragments.size() >= options.max_fragments) {
            break;
        }
    }
    return result;
}

DetectionResult compare_structural(
    std::string_view code_a,
    std::string_view code_b,
    const StructuralOptions& options) {
    auto a_tokens = tokenize(code_a, options.tokenizer);
    auto b_tokens = tokenize(code_b, options.tokenizer);
    auto a_skeleton = structural_skeleton(a_tokens);
    auto b_skeleton = structural_skeleton(b_tokens);

    DetectionResult result;
    result.algorithm = "structural_skeleton";
    result.parameters["k"] = size_param(options.k);

    auto a_hashes = kgram_hashes(a_skeleton, options.k);
    auto b_hashes = kgram_hashes(b_skeleton, options.k);
    if (a_hashes.empty() || b_hashes.empty()) {
        return empty_result(result.algorithm);
    }

    auto a_set = hash_set(a_hashes);
    auto b_set = hash_set(b_hashes);
    const double skeleton_jaccard = jaccard(a_set, b_set);
    const double skeleton_containment = containment(a_set, b_set);
    const double vector_score = cosine_similarity(feature_counts(a_skeleton), feature_counts(b_skeleton));

    result.score = clamp_score(0.65 * skeleton_jaccard + 0.35 * vector_score);
    result.containment = clamp_score(0.65 * skeleton_containment + 0.35 * vector_score);
    result.component_scores["skeleton_jaccard"] = skeleton_jaccard;
    result.component_scores["skeleton_containment"] = skeleton_containment;
    result.component_scores["feature_cosine"] = vector_score;
    return result;
}

DetectionResult compare_code(
    std::string_view code_a,
    std::string_view code_b,
    const CombinedOptions& options) {
    auto ngrams = compare_ngrams(code_a, code_b, options.ngrams);
    auto winnowing = compare_winnowing(code_a, code_b, options.winnowing);
    auto gst = compare_greedy_string_tiling(code_a, code_b, options.gst);
    auto structural = compare_structural(code_a, code_b, options.structural);

    const double total_weight = options.ngram_weight
        + options.winnowing_weight
        + options.gst_weight
        + options.structural_weight;

    DetectionResult result;
    result.algorithm = "combined_classic";
    result.parameters["ngram_weight"] = std::to_string(options.ngram_weight);
    result.parameters["winnowing_weight"] = std::to_string(options.winnowing_weight);
    result.parameters["gst_weight"] = std::to_string(options.gst_weight);
    result.parameters["structural_weight"] = std::to_string(options.structural_weight);

    if (total_weight <= 0.0) {
        result.warnings.push_back("combined detector weights are not positive");
        return result;
    }

    result.score = clamp_score((
        options.ngram_weight * ngrams.score
        + options.winnowing_weight * winnowing.score
        + options.gst_weight * gst.score
        + options.structural_weight * structural.score) / total_weight);

    result.containment = clamp_score((
        options.ngram_weight * ngrams.containment
        + options.winnowing_weight * winnowing.containment
        + options.gst_weight * gst.containment
        + options.structural_weight * structural.containment) / total_weight);

    result.component_scores["token_ngram"] = ngrams.score;
    result.component_scores["winnowing"] = winnowing.score;
    result.component_scores["greedy_string_tiling"] = gst.score;
    result.component_scores["structural_skeleton"] = structural.score;

    result.fragments = gst.fragments;
    if (result.fragments.empty()) {
        result.fragments = winnowing.fragments;
    }
    return result;
}

}  // namespace antiplag::algos
