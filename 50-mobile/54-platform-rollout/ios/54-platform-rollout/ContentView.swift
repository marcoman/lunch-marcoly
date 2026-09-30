import SwiftUI

struct ContentView: View {
    @StateObject private var nav = Navigator()
    @StateObject private var flags = FlagSession()
    @State private var loggedIn = false
    @State private var drawerOpen = false

    var body: some View {
        Group {
            if loggedIn {
                GridScreen(
                    nav: nav,
                    flags: flags,
                    drawerOpen: $drawerOpen,
                    onLogout: {
                        flags.stop()
                        nav.logout()
                        drawerOpen = false
                        loggedIn = false
                    }
                )
            } else {
                LoginScreen { name in
                    if nav.login(name) {
                        flags.start(username: name.trimmingCharacters(in: .whitespacesAndNewlines))
                        loggedIn = true
                    }
                }
            }
        }
        .preferredColorScheme(.dark)
    }
}

private struct LoginScreen: View {
    var onLogin: (String) -> Void
    @State private var name = ""
    @State private var error = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("54-platform-rollout[ios]")
                .font(.caption)
                .foregroundStyle(Color(white: 0.65))
            Text("Login")
                .font(.title2)
            Text(
                "Mobile 2×2 tap lab with LaunchDarkly. Username becomes the context key. " +
                    "Enter a username (no password) to continue."
            )
            .foregroundStyle(Color(white: 0.65))
            TextField("Username", text: $name)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .textFieldStyle(.roundedBorder)
                .onSubmit(submit)
            if error {
                Text("Username is required.")
                    .foregroundStyle(Color(red: 0.9, green: 0.5, blue: 0.5))
            }
            Button("Continue", action: submit)
                .buttonStyle(.borderedProminent)
            Spacer()
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(white: 0.1))
    }

    private func submit() {
        let ok = !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        error = !ok
        if ok { onLogin(name) }
    }
}

private let releaseGreen = Color(red: 0.18, green: 0.49, blue: 0.20)

private struct GridScreen: View {
    @ObservedObject var nav: Navigator
    @ObservedObject var flags: FlagSession
    @Binding var drawerOpen: Bool
    var onLogout: () -> Void

    var body: some View {
        ZStack(alignment: .leading) {
            VStack(alignment: .leading, spacing: 8) {
                Text("54-platform-rollout[ios]")
                    .font(.caption)
                    .foregroundStyle(Color(white: 0.65))
                Text("Name: \(nav.username)")
                    .foregroundStyle(flags.released ? releaseGreen : Color.white)
                Text(flags.released ? "Release: on" : "Release: waiting")
                    .foregroundStyle(flags.released ? releaseGreen : Color.white)
                Text("Current position: \(nav.current.label)")
                Text("Previous position: \(nav.previous?.label ?? "—")")
                Text("Count: \(nav.moveCount)")
                Button("Logout", action: onLogout)
                TapGrid(nav: nav, flags: flags)
                Spacer()
            }
            .padding(.leading, 24)
            .padding(.trailing, 16)
            .padding(.top, 56)
            .padding(.bottom, 16)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .background(Color(white: 0.1))
            .gesture(openDrawerGesture)

            Color.black.opacity(drawerOpen ? 0.45 : 0)
                .ignoresSafeArea()
                .onTapGesture { drawerOpen = false }
                .allowsHitTesting(drawerOpen)

            LabDrawer(nav: nav, flags: flags)
                .frame(width: 300)
                .offset(x: drawerOpen ? 0 : -300)
                .animation(.easeOut(duration: 0.2), value: drawerOpen)

            Color.clear
                .frame(width: 16)
                .contentShape(Rectangle())
                .onTapGesture { drawerOpen = true }
        }
    }

    private var openDrawerGesture: some Gesture {
        DragGesture(minimumDistance: 24)
            .onEnded { value in
                if value.startLocation.x < 28, value.translation.width > 40 {
                    drawerOpen = true
                }
            }
    }
}

private struct LabDrawer: View {
    @ObservedObject var nav: Navigator
    @ObservedObject var flags: FlagSession

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                Text("Lab drawer")
                    .font(.headline)
                Text("Current position: \(nav.current.label)")
                Text("Previous position: \(nav.previous?.label ?? "—")")
                Text("Legal moves: \(nav.legalMoves.map(\.label).joined(separator: ", "))")
                Divider()
                Text("Release: \(flags.released ? "on" : "waiting")")
                Text("Platform: ios")
                Text(flags.hasMobileKey ? "Mobile key: present" : "Mobile key: missing")
                    .foregroundStyle(Color(white: 0.65))
                Text(flags.status)
                    .foregroundStyle(Color(white: 0.65))
                Text("SDK calls")
                    .font(.subheadline)
                Text(flags.sdkLog)
                    .foregroundStyle(Color(white: 0.65))
                Text(
                    "Tap an adjacent square. iOS stays on the previous experience until " +
                        "the targeting rule includes ios. A listener updates this grid without restart."
                )
                .foregroundStyle(Color(white: 0.65))
            }
            .padding(20)
        }
        .frame(maxHeight: .infinity, alignment: .topLeading)
        .background(Color(white: 0.14))
        .shadow(radius: 4)
    }
}

private struct TapGrid: View {
    @ObservedObject var nav: Navigator
    @ObservedObject var flags: FlagSession

    private let cells: [[Cell]] = [
        [Cell(row: .t, col: .l), Cell(row: .t, col: .r)],
        [Cell(row: .b, col: .l), Cell(row: .b, col: .r)],
    ]

    var body: some View {
        let accent: Color? = flags.released ? releaseGreen : nil
        VStack(spacing: 6) {
            ForEach(0..<2, id: \.self) { r in
                HStack(spacing: 6) {
                    ForEach(0..<2, id: \.self) { c in
                        let cell = cells[r][c]
                        let selected = cell == nav.current
                        ZStack {
                            (selected && accent != nil ? accent! : Color(white: 0.18))
                            Text(selected ? "X" : "")
                                .font(.system(size: 28))
                                .foregroundStyle(Color.white)
                        }
                        .frame(width: 120, height: 120)
                        .overlay(
                            Rectangle().stroke(Color(white: 0.35), lineWidth: 1)
                        )
                        .contentShape(Rectangle())
                        .onTapGesture {
                            let before = nav.moveCount
                            nav.tap(cell)
                            if nav.moveCount > before { flags.trackMove() }
                        }
                    }
                }
            }
        }
        .padding(.top, 8)
    }
}

#Preview {
    ContentView()
}
