# Build the 17-scheduled-changes console binary locally in this directory.
TARGET := 17-scheduled-changes
CXX ?= c++
CXXFLAGS := -std=c++20 -Wall -Wextra

REPO_ROOT := $(abspath $(CURDIR)/../../..)
VENV_PYTHON := $(REPO_ROOT)/.venv/bin/python3
CXXFLAGS += -DSCHEDULED_FLAGS_SCRIPT=\"$(CURDIR)/scheduled_flags.py\"
ifneq ($(wildcard $(VENV_PYTHON)),)
    CXXFLAGS += -DDEFAULT_VENV_PYTHON=\"$(VENV_PYTHON)\"
endif

.PHONY: all clean

all: $(TARGET)

$(TARGET): main.cpp flags.cpp flags.hpp scheduled_flags.py
	$(CXX) $(CXXFLAGS) -o $(TARGET) main.cpp flags.cpp $(LDFLAGS)

clean:
	rm -f $(TARGET)
