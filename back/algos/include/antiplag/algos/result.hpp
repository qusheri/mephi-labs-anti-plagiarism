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
    double score = 0.0; // основной коэфф схожести [0;1], где 0 - не похоже, 1 - почти одинаково
    double containment = 0.0; // показывает, насколько один файл содержится в другом (копипаст маленьких кусков кода)
    std::vector<MatchFragment> fragments;
    std::map<std::string, std::string> parameters;
    std::map<std::string, double> component_scores; // оценки отдельных алгосов 
/*
    component_scores["token_ngram"]
    component_scores["winnowing"]
    component_scores["greedy_string_tiling"]
    component_scores["structural_skeleton"]

    score = sum(component_scores[i]{i = "algos_name"}) / n (number of algos)
*/
    std::vector<std::string> warnings;
};

}  // namespace antiplag::algos
