import Combine
import Foundation

/// 2×2 tap navigator for 52-mobile-evaluation.
/// Positions and tap rules match 51-reference.
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
    @Published var username: String = ""
    @Published var current: Cell = Cell(row: .t, col: .l)
    @Published var previous: Cell?
    @Published var moveCount: Int = 0

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

    func tap(_ target: Cell) {
        guard Cell.isOrthogonal(current, target) else { return }
        previous = current
        current = target
        moveCount += 1
    }

    var legalMoves: [Cell] {
        Row.allCases.flatMap { r in Col.allCases.map { Cell(row: r, col: $0) } }
            .filter { Cell.isOrthogonal(current, $0) }
    }

    private func resetGrid() {
        current = Cell(row: .t, col: .l)
        previous = nil
    }
}
