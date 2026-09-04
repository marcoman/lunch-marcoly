import Combine
import Foundation

/// 2×2 tap navigator for 51-reference.
/// Positions are t/l, t/r, b/l, b/r. Moves are orthogonal only.
///
/// 51 has no LaunchDarkly. A later 52 example will initialize the iOS
/// mobile SDK here with `LD_MOBILE_KEY` and a user context key = username.
/// https://launchdarkly.com/docs/sdk/client-side/ios
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
