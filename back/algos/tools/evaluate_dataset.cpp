#include "antiplag/algos/detectors.hpp"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

using antiplag::algos::DetectionResult;

struct Program {
    int id = 0;
    int problem_label = 0;
    std::string code;
};

struct Pair {
    int id_a = 0;
    int id_b = 0;
    int label = 0;
};

struct ScoreRow {
    double score = 0.0;
    int label = 0;
};

struct Metrics {
    std::string name;
    double auc = 0.0;
    double threshold = 0.0;
    double precision = 0.0;
    double recall = 0.0;
    double f1 = 0.0;
    double accuracy = 0.0;
    double positive_mean = 0.0;
    double negative_mean = 0.0;
};

std::string join_path(const std::string& dir, const std::string& file) {
    if (dir.empty() || dir.back() == '/') {
        return dir + file;
    }
    return dir + "/" + file;
}

std::vector<std::vector<std::string>> read_csv(const std::string& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        throw std::runtime_error("cannot open " + path);
    }

    std::vector<std::vector<std::string>> rows;
    std::vector<std::string> row;
    std::string field;
    bool in_quotes = false;
    bool saw_any = false;

    char c = '\0';
    while (input.get(c)) {
        saw_any = true;

        if (in_quotes) {
            if (c == '"') {
                if (input.peek() == '"') {
                    input.get(c);
                    field.push_back('"');
                } else {
                    in_quotes = false;
                }
            } else {
                field.push_back(c);
            }
            continue;
        }

        if (c == '"') {
            in_quotes = true;
        } else if (c == ',') {
            row.push_back(field);
            field.clear();
        } else if (c == '\n') {
            row.push_back(field);
            field.clear();
            rows.push_back(row);
            row.clear();
        } else if (c == '\r') {
            if (input.peek() == '\n') {
                input.get(c);
            }
            row.push_back(field);
            field.clear();
            rows.push_back(row);
            row.clear();
        } else {
            field.push_back(c);
        }
    }

    if (in_quotes) {
        throw std::runtime_error("unterminated quoted field in " + path);
    }
    if (saw_any && (!field.empty() || !row.empty())) {
        row.push_back(field);
        rows.push_back(row);
    }
    return rows;
}

int parse_int(const std::string& value, const std::string& field_name) {
    try {
        std::size_t parsed = 0;
        int result = std::stoi(value, &parsed);
        if (parsed != value.size()) {
            throw std::invalid_argument("trailing bytes");
        }
        return result;
    } catch (const std::exception&) {
        throw std::runtime_error("invalid integer in " + field_name + ": " + value);
    }
}

std::vector<Program> load_programs(const std::string& path) {
    auto rows = read_csv(path);
    if (rows.empty() || rows.front() != std::vector<std::string>{"id", "label", "code"}) {
        throw std::runtime_error("unexpected programs.csv header");
    }

    std::vector<Program> programs;
    programs.reserve(rows.size() - 1);
    for (std::size_t i = 1; i < rows.size(); ++i) {
        if (rows[i].size() != 3) {
            throw std::runtime_error("bad programs.csv row " + std::to_string(i + 1));
        }
        programs.push_back({
            parse_int(rows[i][0], "program id"),
            parse_int(rows[i][1], "program label"),
            rows[i][2],
        });
    }
    return programs;
}

std::vector<Pair> load_pairs(const std::string& path) {
    auto rows = read_csv(path);
    if (rows.empty() || rows.front() != std::vector<std::string>{"id_a", "id_b", "label"}) {
        throw std::runtime_error("unexpected pairs.csv header");
    }

    std::vector<Pair> pairs;
    pairs.reserve(rows.size() - 1);
    for (std::size_t i = 1; i < rows.size(); ++i) {
        if (rows[i].size() != 3) {
            throw std::runtime_error("bad pairs.csv row " + std::to_string(i + 1));
        }
        pairs.push_back({
            parse_int(rows[i][0], "pair id_a"),
            parse_int(rows[i][1], "pair id_b"),
            parse_int(rows[i][2], "pair label"),
        });
    }
    return pairs;
}

double mean_score_for_label(const std::vector<ScoreRow>& rows, int label) {
    double sum = 0.0;
    std::size_t count = 0;
    for (const auto& row : rows) {
        if (row.label == label) {
            sum += row.score;
            ++count;
        }
    }
    return count == 0 ? 0.0 : sum / static_cast<double>(count);
}

double roc_auc(std::vector<ScoreRow> rows) {
    const std::size_t positives = static_cast<std::size_t>(
        std::count_if(rows.begin(), rows.end(), [](const auto& row) { return row.label == 1; }));
    const std::size_t negatives = rows.size() - positives;
    if (positives == 0 || negatives == 0) {
        return 0.0;
    }

    std::sort(rows.begin(), rows.end(), [](const auto& lhs, const auto& rhs) {
        return lhs.score < rhs.score;
    });

    double positive_rank_sum = 0.0;
    std::size_t i = 0;
    while (i < rows.size()) {
        std::size_t j = i + 1;
        while (j < rows.size() && rows[j].score == rows[i].score) {
            ++j;
        }
        const double first_rank = static_cast<double>(i + 1);
        const double last_rank = static_cast<double>(j);
        const double average_rank = (first_rank + last_rank) / 2.0;
        for (std::size_t k = i; k < j; ++k) {
            if (rows[k].label == 1) {
                positive_rank_sum += average_rank;
            }
        }
        i = j;
    }

    const double positive_count = static_cast<double>(positives);
    const double negative_count = static_cast<double>(negatives);
    return (positive_rank_sum - positive_count * (positive_count + 1.0) / 2.0)
        / (positive_count * negative_count);
}

Metrics compute_metrics(const std::string& name, std::vector<ScoreRow> rows) {
    const int positives = static_cast<int>(
        std::count_if(rows.begin(), rows.end(), [](const auto& row) { return row.label == 1; }));
    const int negatives = static_cast<int>(rows.size()) - positives;
    if (positives == 0 || negatives == 0) {
        throw std::runtime_error("metrics require both positive and negative labels");
    }

    std::sort(rows.begin(), rows.end(), [](const auto& lhs, const auto& rhs) {
        return lhs.score > rhs.score;
    });

    double best_j = -std::numeric_limits<double>::infinity();
    double best_threshold = rows.front().score;
    int best_tp = 0;
    int best_fp = 0;
    int tp = 0;
    int fp = 0;

    std::size_t i = 0;
    while (i < rows.size()) {
        const double threshold = rows[i].score;
        std::size_t j = i;
        while (j < rows.size() && rows[j].score == threshold) {
            if (rows[j].label == 1) {
                ++tp;
            } else {
                ++fp;
            }
            ++j;
        }

        const double tpr = static_cast<double>(tp) / static_cast<double>(positives);
        const double fpr = static_cast<double>(fp) / static_cast<double>(negatives);
        const double youden_j = tpr - fpr;
        if (youden_j > best_j) {
            best_j = youden_j;
            best_threshold = threshold;
            best_tp = tp;
            best_fp = fp;
        }
        i = j;
    }

    const int fn = positives - best_tp;
    const int tn = negatives - best_fp;
    const double precision = best_tp + best_fp == 0
        ? 0.0
        : static_cast<double>(best_tp) / static_cast<double>(best_tp + best_fp);
    const double recall = best_tp + fn == 0
        ? 0.0
        : static_cast<double>(best_tp) / static_cast<double>(best_tp + fn);
    const double f1 = precision + recall == 0.0
        ? 0.0
        : 2.0 * precision * recall / (precision + recall);
    const double accuracy = static_cast<double>(best_tp + tn) / static_cast<double>(rows.size());

    Metrics metrics;
    metrics.name = name;
    metrics.auc = roc_auc(rows);
    metrics.threshold = best_threshold;
    metrics.precision = precision;
    metrics.recall = recall;
    metrics.f1 = f1;
    metrics.accuracy = accuracy;
    metrics.positive_mean = mean_score_for_label(rows, 1);
    metrics.negative_mean = mean_score_for_label(rows, 0);
    return metrics;
}

void print_metrics(const std::vector<Metrics>& metrics) {
    std::cout << "\n"
              << std::left << std::setw(24) << "algorithm"
              << std::right << std::setw(9) << "auc"
              << std::setw(11) << "thr"
              << std::setw(11) << "prec"
              << std::setw(11) << "recall"
              << std::setw(11) << "f1"
              << std::setw(11) << "acc"
              << std::setw(12) << "pos_mean"
              << std::setw(12) << "neg_mean"
              << '\n';

    std::cout << std::string(112, '-') << '\n';
    std::cout << std::fixed << std::setprecision(4);
    for (const auto& row : metrics) {
        std::cout << std::left << std::setw(24) << row.name
                  << std::right << std::setw(9) << row.auc
                  << std::setw(11) << row.threshold
                  << std::setw(11) << row.precision
                  << std::setw(11) << row.recall
                  << std::setw(11) << row.f1
                  << std::setw(11) << row.accuracy
                  << std::setw(12) << row.positive_mean
                  << std::setw(12) << row.negative_mean
                  << '\n';
    }
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const std::string dataset_dir = argc > 1 ? argv[1] : "../../test_data";
        const auto programs = load_programs(join_path(dataset_dir, "programs.csv"));
        const auto pairs = load_pairs(join_path(dataset_dir, "pairs.csv"));

        std::unordered_map<int, Program> by_id;
        by_id.reserve(programs.size());
        std::map<int, int> class_counts;
        for (const auto& program : programs) {
            by_id.emplace(program.id, program);
            class_counts[program.problem_label] += 1;
        }

        int positive_pairs = 0;
        int negative_pairs = 0;
        for (const auto& pair : pairs) {
            positive_pairs += pair.label == 1 ? 1 : 0;
            negative_pairs += pair.label == 0 ? 1 : 0;
        }

        std::cout << "Dataset: " << dataset_dir << '\n';
        std::cout << "Programs: " << programs.size()
                  << " | classes: " << class_counts.size()
                  << " | pairs: " << pairs.size()
                  << " (" << positive_pairs << " positive, "
                  << negative_pairs << " negative)\n";
        std::cout << std::flush;

        struct Detector {
            std::string name;
            std::function<DetectionResult(const std::string&, const std::string&)> run;
        };

        antiplag::algos::NGramOptions ngram_options;
        antiplag::algos::WinnowingOptions winnowing_options;
        antiplag::algos::GreedyStringTilingOptions gst_options;
        antiplag::algos::StructuralOptions structural_options;
        antiplag::algos::CombinedOptions combined_options;

        const std::vector<Detector> detectors = {
            {"token_ngram", [=](const auto& a, const auto& b) {
                 return antiplag::algos::compare_ngrams(a, b, ngram_options);
             }},
            {"winnowing", [=](const auto& a, const auto& b) {
                 return antiplag::algos::compare_winnowing(a, b, winnowing_options);
             }},
            {"greedy_string_tiling", [=](const auto& a, const auto& b) {
                 return antiplag::algos::compare_greedy_string_tiling(a, b, gst_options);
             }},
            {"structural_skeleton", [=](const auto& a, const auto& b) {
                 return antiplag::algos::compare_structural(a, b, structural_options);
             }},
            {"combined_classic", [=](const auto& a, const auto& b) {
                 return antiplag::algos::compare_code(a, b, combined_options);
             }},
        };

        std::map<std::string, std::vector<ScoreRow>> scores;
        for (const auto& detector : detectors) {
            scores[detector.name].reserve(pairs.size());
        }

        for (std::size_t i = 0; i < pairs.size(); ++i) {
            const auto& pair = pairs[i];
            const auto a_it = by_id.find(pair.id_a);
            const auto b_it = by_id.find(pair.id_b);
            if (a_it == by_id.end() || b_it == by_id.end()) {
                throw std::runtime_error("pair references unknown program id");
            }

            for (const auto& detector : detectors) {
                const auto result = detector.run(a_it->second.code, b_it->second.code);
                scores[detector.name].push_back({result.score, pair.label});
            }

            if ((i + 1) % 100 == 0 || i + 1 == pairs.size()) {
                std::cerr << "evaluated " << (i + 1) << "/" << pairs.size() << " pairs\n";
            }
        }

        std::vector<Metrics> metrics;
        metrics.reserve(detectors.size());
        for (const auto& detector : detectors) {
            metrics.push_back(compute_metrics(detector.name, scores[detector.name]));
        }

        print_metrics(metrics);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
