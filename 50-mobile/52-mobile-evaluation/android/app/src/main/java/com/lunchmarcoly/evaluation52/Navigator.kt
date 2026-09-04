package com.lunchmarcoly.evaluation52

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/**
 * 2×2 tap navigator for 52-mobile-evaluation.
 * Positions and tap rules match 51-reference.
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

    fun tap(target: Cell) {
        if (!isOrthogonal(current, target)) return
        previous = current
        current = target
        moveCount += 1
    }

    fun legalMoves(): List<Cell> =
        Row.entries.flatMap { r -> Col.entries.map { c -> Cell(r, c) } }
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
