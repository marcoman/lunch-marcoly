package com.lunchmarcoly.experiment53

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/**
 * Preserves the 51/52 2×2 navigator: only orthogonal adjacent taps move X.
 */
enum class Row { T, B }

enum class Col { L, R }

data class Cell(val row: Row, val col: Col) {
    fun label(): String = "${row.name.lowercase()}/${col.name.lowercase()}"
}

class Navigator {
    var username by mutableStateOf("")
        private set
    var current by mutableStateOf(Cell(Row.T, Col.L))
        private set
    var previous by mutableStateOf<Cell?>(null)
        private set
    var moveCount by mutableIntStateOf(0)
        private set

    fun login(name: String): Boolean {
        val trimmed = name.trim()
        if (trimmed.isEmpty()) return false
        username = trimmed
        resetGrid()
        return true
    }

    fun logout() {
        username = ""
        resetGrid()
    }

    fun tap(target: Cell): Boolean {
        if (!isOrthogonal(current, target)) return false
        previous = current
        current = target
        moveCount += 1
        return true
    }

    fun legalMoves(): List<Cell> =
        Row.entries.flatMap { row -> Col.entries.map { col -> Cell(row, col) } }
            .filter { isOrthogonal(current, it) }

    private fun resetGrid() {
        current = Cell(Row.T, Col.L)
        previous = null
    }

    companion object {
        fun isOrthogonal(a: Cell, b: Cell): Boolean {
            val rowDelta = kotlin.math.abs(a.row.ordinal - b.row.ordinal)
            val colDelta = kotlin.math.abs(a.col.ordinal - b.col.ordinal)
            return rowDelta + colDelta == 1
        }
    }
}
