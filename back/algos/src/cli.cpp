#include "antiplag/algos/detectors.hpp"

#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {

std::string read_file(const std::string& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        throw std::runtime_error("cannot open file: " + path);
    }
    std::ostringstream buffer;
    buffer << input.rdbuf();
    return buffer.str();
}

std::string json_escape(const std::string& value) {
    std::string escaped;
    escaped.reserve(value.size() + 8);
    for (char ch : value) {
        switch (ch) {
            case '\\':
                escaped += "\\\\";
                break;
            case '"':
                escaped += "\\\"";
                break;
            case '\n':
                escaped += "\\n";
                break;
            case '\r':
                escaped += "\\r";
                break;
            case '\t':
                escaped += "\\t";
                break;
            default:
                escaped += ch;
                break;
        }
    }
    return escaped;
}

void print_usage() {
    std::cerr << "Usage: antiplag_algos_cli <file_a> <file_b>\n";
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        print_usage();
        return 2;
    }

    try {
        const std::string code_a = read_file(argv[1]);
        const std::string code_b = read_file(argv[2]);
        const auto result = antiplag::algos::compare_code(code_a, code_b);

        std::cout << "{";
        std::cout << "\"algorithm\":\"" << json_escape(result.algorithm) << "\",";
        std::cout << "\"score\":" << result.score << ",";
        std::cout << "\"containment\":" << result.containment << ",";

        std::cout << "\"component_scores\":{";
        bool first_component = true;
        for (const auto& [name, score] : result.component_scores) {
            if (!first_component) {
                std::cout << ",";
            }
            first_component = false;
            std::cout << "\"" << json_escape(name) << "\":" << score;
        }
        std::cout << "},";

        std::cout << "\"fragments\":[";
        bool first_fragment = true;
        for (const auto& fragment : result.fragments) {
            if (!first_fragment) {
                std::cout << ",";
            }
            first_fragment = false;
            std::cout << "{";
            std::cout << "\"file_a_line_start\":" << fragment.file_a_line_start << ",";
            std::cout << "\"file_a_line_end\":" << fragment.file_a_line_end << ",";
            std::cout << "\"file_b_line_start\":" << fragment.file_b_line_start << ",";
            std::cout << "\"file_b_line_end\":" << fragment.file_b_line_end << ",";
            std::cout << "\"explanation\":\"" << json_escape(fragment.explanation) << "\"";
            std::cout << "}";
        }
        std::cout << "],";

        std::cout << "\"warnings\":[";
        bool first_warning = true;
        for (const auto& warning : result.warnings) {
            if (!first_warning) {
                std::cout << ",";
            }
            first_warning = false;
            std::cout << "\"" << json_escape(warning) << "\"";
        }
        std::cout << "]";

        std::cout << "}\n";
        return 0;
    } catch (const std::exception& exc) {
        std::cerr << exc.what() << "\n";
        return 1;
    }
}
