#include "antiplag/algos/tokenizer.hpp"

#include <algorithm>
#include <cctype>
#include <string>
#include <unordered_set>

namespace antiplag::algos {
namespace {

bool is_ident_start(unsigned char c) {
    return std::isalpha(c) || c == '_';
}

bool is_ident_part(unsigned char c) {
    return std::isalnum(c) || c == '_';
}

bool is_digit(unsigned char c) {
    return std::isdigit(c);
}

std::string lowercase(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return value;
}

const std::unordered_set<std::string>& keywords() {
    static const std::unordered_set<std::string> words = {
        "alignas", "alignof", "and", "as", "asm", "assert", "auto", "await",
        "bool", "break", "case", "catch", "char", "class", "concept", "const",
        "constexpr", "continue", "decltype", "def", "default", "del", "do",
        "double", "elif", "else", "enum", "except", "explicit", "export",
        "extends", "extern", "false", "finally", "float", "for", "friend",
        "from", "function", "goto", "if", "implements", "import", "in",
        "inline", "int", "interface", "lambda", "let", "long", "match",
        "mutable", "namespace", "new", "noexcept", "not", "nullptr", "operator",
        "or", "pass", "private", "protected", "public", "raise", "register",
        "requires", "return", "short", "signed", "sizeof", "static", "struct",
        "switch", "template", "this", "throw", "throws", "true", "try",
        "typedef", "typename", "union", "unsigned", "using", "var", "virtual",
        "void", "volatile", "while", "with", "yield",
    };
    return words;
}

bool is_keyword(std::string value) {
    return keywords().find(lowercase(std::move(value))) != keywords().end();
}

std::string normalized_for(TokenKind kind, std::string text, const TokenizationOptions& options) {
    if (kind == TokenKind::Identifier && options.normalize_identifiers) {
        return "ID";
    }
    if (kind == TokenKind::Number && options.normalize_literals) {
        return "NUM";
    }
    if (kind == TokenKind::String && options.normalize_literals) {
        return "STR";
    }
    if (kind == TokenKind::Keyword && options.lowercase_keywords) {
        return lowercase(std::move(text));
    }
    return text;
}

bool starts_with(std::string_view text, std::size_t pos, std::string_view prefix) {
    return pos + prefix.size() <= text.size() && text.substr(pos, prefix.size()) == prefix;
}

bool is_separator(char c) {
    switch (c) {
        case '(':
        case ')':
        case '{':
        case '}':
        case '[':
        case ']':
        case ';':
        case ',':
        case '.':
        case ':':
            return true;
        default:
            return false;
    }
}

const std::vector<std::string>& operators() {
    static const std::vector<std::string> ops = {
        "<<=", ">>=", "===", "!==", "->*", "...", "::", "->", "++", "--", "==",
        "!=", "<=", ">=", "&&", "||", "+=", "-=", "*=", "/=", "%=", "&=", "|=",
        "^=", "<<", ">>", "**", "=>", "+", "-", "*", "/", "%", "=", "<", ">",
        "!", "&", "|", "^", "~", "?",
    };
    return ops;
}

void add_token(
    std::vector<Token>& tokens,
    TokenKind kind,
    std::string text,
    std::size_t byte_start,
    std::size_t byte_end,
    std::size_t line_start,
    std::size_t line_end,
    const TokenizationOptions& options) {
    Token token;
    token.kind = kind;
    token.normalized = normalized_for(kind, text, options);
    token.text = std::move(text);
    token.span.byte_start = byte_start;
    token.span.byte_end = byte_end;
    token.span.line_start = line_start;
    token.span.line_end = line_end;
    tokens.push_back(std::move(token));
}

}  // namespace

std::vector<Token> tokenize(std::string_view code, const TokenizationOptions& options) {
    std::vector<Token> tokens;
    std::size_t i = 0;
    std::size_t line = 1;

    while (i < code.size()) {
        const unsigned char c = static_cast<unsigned char>(code[i]);

        if (std::isspace(c)) {
            if (code[i] == '\n') {
                ++line;
            }
            ++i;
            continue;
        }

        if (starts_with(code, i, "//")) {
            i += 2;
            while (i < code.size() && code[i] != '\n') {
                ++i;
            }
            continue;
        }

        if (starts_with(code, i, "/*")) {
            i += 2;
            while (i + 1 < code.size() && !starts_with(code, i, "*/")) {
                if (code[i] == '\n') {
                    ++line;
                }
                ++i;
            }
            i = std::min(i + 2, code.size());
            continue;
        }

        if (code[i] == '#') {
            ++i;
            while (i < code.size() && code[i] != '\n') {
                ++i;
            }
            continue;
        }

        const std::size_t start = i;
        const std::size_t line_start = line;

        if (is_ident_start(c)) {
            ++i;
            while (i < code.size() && is_ident_part(static_cast<unsigned char>(code[i]))) {
                ++i;
            }
            std::string text(code.substr(start, i - start));
            const TokenKind kind = is_keyword(text) ? TokenKind::Keyword : TokenKind::Identifier;
            add_token(tokens, kind, std::move(text), start, i, line_start, line, options);
            continue;
        }

        if (is_digit(c)) {
            ++i;
            while (i < code.size()) {
                const unsigned char current = static_cast<unsigned char>(code[i]);
                if (!std::isalnum(current) && code[i] != '.' && code[i] != '_' && code[i] != '+' && code[i] != '-') {
                    break;
                }
                if ((code[i] == '+' || code[i] == '-') && !(code[i - 1] == 'e' || code[i - 1] == 'E')) {
                    break;
                }
                ++i;
            }
            std::string text(code.substr(start, i - start));
            add_token(tokens, TokenKind::Number, std::move(text), start, i, line_start, line, options);
            continue;
        }

        if (code[i] == '"' || code[i] == '\'' || code[i] == '`') {
            const char quote = code[i];
            ++i;
            const bool triple = i + 1 < code.size() && code[i] == quote && code[i + 1] == quote;
            if (triple) {
                i += 2;
            }
            while (i < code.size()) {
                if (code[i] == '\n') {
                    ++line;
                }
                if (!triple && code[i] == '\\') {
                    i = std::min(i + 2, code.size());
                    continue;
                }
                if (triple && i + 2 < code.size() && code[i] == quote && code[i + 1] == quote && code[i + 2] == quote) {
                    i += 3;
                    break;
                }
                if (!triple && code[i] == quote) {
                    ++i;
                    break;
                }
                ++i;
            }
            std::string text(code.substr(start, i - start));
            add_token(tokens, TokenKind::String, std::move(text), start, i, line_start, line, options);
            continue;
        }

        bool matched_operator = false;
        for (const auto& op : operators()) {
            if (starts_with(code, i, op)) {
                i += op.size();
                add_token(tokens, TokenKind::Operator, op, start, i, line_start, line, options);
                matched_operator = true;
                break;
            }
        }
        if (matched_operator) {
            continue;
        }

        if (is_separator(code[i])) {
            ++i;
            std::string text(code.substr(start, 1));
            add_token(tokens, TokenKind::Separator, std::move(text), start, i, line_start, line, options);
            continue;
        }

        ++i;
        std::string text(code.substr(start, 1));
        add_token(tokens, TokenKind::Unknown, std::move(text), start, i, line_start, line, options);
    }

    return tokens;
}

std::vector<std::string> normalized_values(const std::vector<Token>& tokens) {
    std::vector<std::string> values;
    values.reserve(tokens.size());
    for (const auto& token : tokens) {
        values.push_back(token.normalized);
    }
    return values;
}

std::string to_string(TokenKind kind) {
    switch (kind) {
        case TokenKind::Keyword:
            return "keyword";
        case TokenKind::Identifier:
            return "identifier";
        case TokenKind::Number:
            return "number";
        case TokenKind::String:
            return "string";
        case TokenKind::Operator:
            return "operator";
        case TokenKind::Separator:
            return "separator";
        case TokenKind::Unknown:
            return "unknown";
    }
    return "unknown";
}

}  // namespace antiplag::algos
