CXX ?= c++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -Wpedantic -O2

BUILD_DIR := build
INCLUDES := -Iinclude
SOURCES := src/tokenizer.cpp src/detectors.cpp
TEST_SOURCES := tests/algos_test.cpp
TEST_BINARY := $(BUILD_DIR)/antiplag_algos_tests
EVAL_SOURCES := tools/evaluate_dataset.cpp
EVAL_BINARY := $(BUILD_DIR)/evaluate_dataset

.PHONY: all test evaluate dataset clean

all: test

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(TEST_BINARY): $(SOURCES) $(TEST_SOURCES) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(INCLUDES) $(SOURCES) $(TEST_SOURCES) -o $(TEST_BINARY)

$(EVAL_BINARY): $(SOURCES) $(EVAL_SOURCES) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) $(INCLUDES) $(SOURCES) $(EVAL_SOURCES) -o $(EVAL_BINARY)

test: $(TEST_BINARY)
	./$(TEST_BINARY)

evaluate: $(EVAL_BINARY)

dataset: $(EVAL_BINARY)
	./$(EVAL_BINARY) ../../test_data

clean:
	rm -rf $(BUILD_DIR)
