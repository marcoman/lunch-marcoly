import Combine
import Foundation

/// The shared 2×2 navigator. A move succeeds only when the tapped cell is
/// orthogonally adjacent to the current cell.
enum Row: String, CaseIterable {
    case t
    case b
}

enum Col: String, CaseIterable {
    case l
    case r
}

struct Cell: Equatable, Hashable {
    var row: Row
    var col: Col

    var label: String { "\(row.rawValue)/\(col.rawValue)" }

    static func isOrthogonal(_ a: Cell, _ b: Cell) -> Bool {
        let rowDelta = abs(Row.allCases.firstIndex(of: a.row)! - Row.allCases.firstIndex(of: b.row)!)
        let colDelta = abs(Col.allCases.firstIndex(of: a.col)! - Col.allCases.firstIndex(of: b.col)!)
        return rowDelta + colDelta == 1
    }
}

final class Navigator: ObservableObject {
    @Published var username = ""
    @Published var current = Cell(row: .t, col: .l)
    @Published var previous: Cell?
    @Published var moveCount = 0

    func login(_ name: String) -> Bool {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return false }
        username = trimmed
        resetGrid()
        return true
    }

    func logout() {
        username = ""
        resetGrid()
    }

    /// Returns true only for a successful orthogonal move. Callers use this
    /// boundary to emit the conversion event without counting invalid taps.
    @discardableResult
    func tap(_ target: Cell) -> Bool {
        guard Cell.isOrthogonal(current, target) else { return false }
        previous = current
        current = target
        moveCount += 1
        return true
    }

    var legalMoves: [Cell] {
        Row.allCases.flatMap { row in
            Col.allCases.map { Cell(row: row, col: $0) }
        }
        .filter { Cell.isOrthogonal(current, $0) }
    }

    private func resetGrid() {
        current = Cell(row: .t, col: .l)
        previous = nil
        moveCount = 0
    }
}
