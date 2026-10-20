# Build the 14-multi-context-targeting console binary locally in this directory.
TARGET := 14-multi-context-targeting
CXX ?= c++
CXXFLAGS := -std=c++20 -Wall -Wextra

# LaunchDarkly evaluation delegates to the repository Python server SDK helper.
# https://launchdarkly.com/docs/sdk/server-side/python
REPO_ROOT := $(abspath $(CURDIR)/../../..)
VENV_PYTHON := $(REPO_ROOT)/.venv/bin/python3
EVALUATE_FLAGS_SCRIPT := $(CURDIR)/evaluate_flags.py
CXXFLAGS += -DEVALUATE_FLAGS_SCRIPT=\"$(EVALUATE_FLAGS_SCRIPT)\"
ifneq ($(wildcard $(VENV_PYTHON)),)
CXXFLAGS += -DDEFAULT_VENV_PYTHON=\"$(VENV_PYTHON)\"
endif

.PHONY: all clean

all: $(TARGET)

$(TARGET): main.cpp flags.cpp flags.hpp
	$(CXX) $(CXXFLAGS) -o $(TARGET) main.cpp flags.cpp

clean:
	rm -f $(TARGET)
