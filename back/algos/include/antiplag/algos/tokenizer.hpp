#pragma once

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

namespace antiplag::algos {

enum class TokenKind {
    Keyword,
    Identifier,
    Number,
    String,
    Operator,
    Separator,
    Unknown,
};

struct SourceSpan {
    std::size_t byte_start = 0;
    std::size_t byte_end = 0;
    std::size_t line_start = 1;
    std::size_t line_end = 1;
};

struct Token {
    TokenKind kind = TokenKind::Unknown;
    std::string text;
    std::string normalized;
    SourceSpan span;
};

struct TokenizationOptions {
    bool normalize_identifiers = true;
    bool normalize_literals = true;
    bool lowercase_keywords = true;
};

std::vector<Token> tokenize(
    std::string_view code,
    const TokenizationOptions& options = {});

std::vector<std::string> normalized_values(const std::vector<Token>& tokens);

std::string to_string(TokenKind kind);

}  // namespace antiplag::algos
