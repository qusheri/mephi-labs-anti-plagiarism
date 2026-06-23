#pragma once

#include <cstddef>
#include <map>
#include <string>
#include <vector>

namespace antiplag::algos {

struct MatchFragment {
    std::size_t file_a_token_start = 0;
    std::size_t file_a_token_end = 0;
    std::size_t file_b_token_start = 0;
    std::size_t file_b_token_end = 0;

    std::size_t file_a_line_start = 0;
    std::size_t file_a_line_end = 0;
    std::size_t file_b_line_start = 0;
    std::size_t file_b_line_end = 0;

    std::string explanation;
};

struct DetectionResult {
    std::string algorithm;
    double score = 0.0;
    double containment = 0.0;
    std::vector<MatchFragment> fragments;
    std::map<std::string, std::string> parameters;
    std::map<std::string, double> component_scores;
    std::vector<std::string> warnings;
};

}  // namespace antiplag::algos
