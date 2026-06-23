#include "antiplag/algos/detectors.hpp"
#include "antiplag/algos/tokenizer.hpp"

#include <cstdlib>
#include <iostream>
#include <string>

namespace {

void require(bool condition, const std::string& message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(1);
    }
}

void test_tokenizer_normalizes_identifiers_and_literals() {
    const auto tokens = antiplag::algos::tokenize("int result = value + 42; // comment\n");
    bool has_id = false;
    bool has_num = false;
    for (const auto& token : tokens) {
        has_id = has_id || token.normalized == "ID";
        has_num = has_num || token.normalized == "NUM";
        require(token.text != "comment", "comments must not be tokenized");
    }
    require(has_id, "identifier normalization");
    require(has_num, "number normalization");
}

void test_type_1_and_type_2_similarity() {
    const std::string a = R"cpp(
        int main() {
            int result = 0;
            for (int i = 0; i < 10; ++i) {
                result += i;
            }
            return result;
        }
    )cpp";

    const std::string b = R"cpp(
        // formatting and names changed
        int main(){int answer=5-5; for(int index=0; index<10; ++index){answer += index;} return answer;}
    )cpp";

    antiplag::algos::NGramOptions options;
    options.k = 4;
    const auto ngrams = antiplag::algos::compare_ngrams(a, b, options);
    require(ngrams.score > 0.55, "n-grams should catch Type-1/Type-2 clones");

    antiplag::algos::GreedyStringTilingOptions gst_options;
    gst_options.min_match_length = 5;
    const auto gst = antiplag::algos::compare_greedy_string_tiling(a, b, gst_options);
    require(gst.score > 0.60, "GST should catch normalized copied token runs");
    require(!gst.fragments.empty(), "GST should produce report fragments");
}

void test_moved_blocks_are_found() {
    const std::string a = R"cpp(
        int sum(int n) {
            int s = 0;
            for (int i = 0; i <= n; ++i) {
                s += i;
            }
            return s;
        }

        int square(int x) {
            return x * x;
        }
    )cpp";

    const std::string b = R"cpp(
        int square(int value) {
            return value * value;
        }

        int sum(int limit) {
            int total = 0;
            for (int pos = 0; pos <= limit; ++pos) {
                total += pos;
            }
            return total;
        }
    )cpp";

    antiplag::algos::GreedyStringTilingOptions options;
    options.min_match_length = 5;
    const auto result = antiplag::algos::compare_greedy_string_tiling(a, b, options);
    require(result.score > 0.80, "GST should tolerate moved functions/blocks");
    require(result.fragments.size() >= 2, "moved blocks should be visible as fragments");
}

void test_structural_detector_tolerates_loop_rewrite() {
    const std::string a = R"cpp(
        int sum(int n) {
            int s = 0;
            for (int i = 0; i < n; ++i) {
                if (i % 2 == 0) {
                    s += i;
                }
            }
            return s;
        }
    )cpp";

    const std::string b = R"cpp(
        int sum(int n) {
            int s = 0;
            int i = 0;
            while (i < n) {
                if (i % 2 == 0) {
                    s += i;
                }
                ++i;
            }
            return s;
        }
    )cpp";

    const auto result = antiplag::algos::compare_structural(a, b);
    require(result.score > 0.55, "structural detector should partially catch for-to-while rewrites");
}

void test_combined_score_is_reasonable_for_unrelated_code() {
    const std::string a = R"cpp(
        int fibonacci(int n) {
            if (n <= 1) return n;
            return fibonacci(n - 1) + fibonacci(n - 2);
        }
    )cpp";

    const std::string b = R"cpp(
        class Parser {
        public:
            bool parse(const std::string& text) {
                return !text.empty() && text[0] == '{';
            }
        };
    )cpp";

    const auto result = antiplag::algos::compare_code(a, b);
    require(result.score < 0.55, "unrelated code should not look highly plagiarized");
}

}  // namespace

int main() {
    test_tokenizer_normalizes_identifiers_and_literals();
    test_type_1_and_type_2_similarity();
    test_moved_blocks_are_found();
    test_structural_detector_tolerates_loop_rewrite();
    test_combined_score_is_reasonable_for_unrelated_code();
    std::cout << "All antiplag algorithm tests passed\n";
    return 0;
}
