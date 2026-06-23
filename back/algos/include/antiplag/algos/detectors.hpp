#pragma once

#include "antiplag/algos/result.hpp"
#include "antiplag/algos/tokenizer.hpp"

#include <cstddef>
#include <string_view>

namespace antiplag::algos {

struct NGramOptions {
    std::size_t k = 5;
    TokenizationOptions tokenizer;
};

struct WinnowingOptions {
    std::size_t k = 5;
    std::size_t window = 4;
    TokenizationOptions tokenizer;
};

struct GreedyStringTilingOptions {
    std::size_t min_match_length = 8;
    std::size_t max_fragments = 50;
    TokenizationOptions tokenizer;
};

struct StructuralOptions {
    std::size_t k = 4;
    TokenizationOptions tokenizer;
};

struct CombinedOptions {
    NGramOptions ngrams;
    WinnowingOptions winnowing;
    GreedyStringTilingOptions gst;
    StructuralOptions structural;

    double ngram_weight = 0.20;
    double winnowing_weight = 0.25;
    double gst_weight = 0.35;
    double structural_weight = 0.20;
};

DetectionResult compare_ngrams(
    std::string_view code_a,
    std::string_view code_b,
    const NGramOptions& options = {});

DetectionResult compare_winnowing(
    std::string_view code_a,
    std::string_view code_b,
    const WinnowingOptions& options = {});

DetectionResult compare_greedy_string_tiling(
    std::string_view code_a,
    std::string_view code_b,
    const GreedyStringTilingOptions& options = {});

DetectionResult compare_structural(
    std::string_view code_a,
    std::string_view code_b,
    const StructuralOptions& options = {});

DetectionResult compare_code(
    std::string_view code_a,
    std::string_view code_b,
    const CombinedOptions& options = {});

}  // namespace antiplag::algos
