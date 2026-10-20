# Build the 16-percentage-rollout console binary locally in this directory.
TARGET := 16-percentage-rollout
CXX ?= c++
CXXFLAGS := -std=c++20 -Wall -Wextra

REPO_ROOT := $(abspath $(CURDIR)/../../..)
VENV_PYTHON := $(REPO_ROOT)/.venv/bin/python3
CXXFLAGS += -DEVALUATE_FLAGS_SCRIPT=\"$(CURDIR)/evaluate_flags.py\"
ifneq ($(wildcard $(VENV_PYTHON)),)
    CXXFLAGS += -DDEFAULT_VENV_PYTHON=\"$(VENV_PYTHON)\"
endif

.PHONY: all clean

all: $(TARGET)

$(TARGET): main.cpp flags.cpp flags.hpp
	$(CXX) $(CXXFLAGS) -o $(TARGET) main.cpp flags.cpp $(LDFLAGS)

clean:
	rm -f $(TARGET)
