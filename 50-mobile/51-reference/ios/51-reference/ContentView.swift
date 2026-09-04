import SwiftUI

struct ContentView: View {
    @StateObject private var nav = Navigator()
    @State private var loggedIn = false
    @State private var drawerOpen = false

    var body: some View {
        Group {
            if loggedIn {
                GridScreen(
                    nav: nav,
                    drawerOpen: $drawerOpen,
                    onLogout: {
                        nav.logout()
                        drawerOpen = false
                        loggedIn = false
                    }
                )
            } else {
                LoginScreen { name in
                    if nav.login(name) {
                        loggedIn = true
                    }
                }
            }
        }
        .preferredColorScheme(.light)
    }
}

private struct LoginScreen: View {
    var onLogin: (String) -> Void
    @State private var name = ""
    @State private var error = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("51-reference[ios]")
                .font(.caption)
                .foregroundStyle(Color(white: 0.4))
            Text("Login")
                .font(.title2)
            Text(
                "This is the mobile 2×2 tap lab. It is not the web WASD grid. " +
                    "Enter a username (no password) to continue."
            )
            .foregroundStyle(Color(white: 0.4))
            TextField("Username", text: $name)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .textFieldStyle(.roundedBorder)
                .onSubmit(submit)
            if error {
                Text("Username is required.")
                    .foregroundStyle(Color(red: 0.78, green: 0.16, blue: 0.16))
            }
            Button("Continue", action: submit)
                .buttonStyle(.borderedProminent)
            Spacer()
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Color(white: 0.98))
    }

    private func submit() {
        let ok = !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        error = !ok
        if ok { onLogin(name) }
    }
}

private struct GridScreen: View {
    @ObservedObject var nav: Navigator
    @Binding var drawerOpen: Bool
    var onLogout: () -> Void

    var body: some View {
        ZStack(alignment: .leading) {
            VStack(alignment: .leading, spacing: 8) {
                Text("51-reference[ios]")
                    .font(.caption)
                    .foregroundStyle(Color(white: 0.4))
                Text("Name: \(nav.username)")
                Text("Current position: \(nav.current.label)")
                Text("Previous position: \(nav.previous?.label ?? "—")")
                Button("Logout", action: onLogout)
                TapGrid(nav: nav)
                Spacer()
            }
            .padding(.leading, 24)
            .padding(.trailing, 16)
            .padding(.top, 56)
            .padding(.bottom, 16)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .background(Color(white: 0.98))
            .gesture(openDrawerGesture)

            Color.black.opacity(drawerOpen ? 0.25 : 0)
                .ignoresSafeArea()
                .onTapGesture { drawerOpen = false }
                .allowsHitTesting(drawerOpen)

            LabDrawer(nav: nav)
                .frame(width: 280)
                .offset(x: drawerOpen ? 0 : -280)
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

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Lab drawer")
                .font(.headline)
            Text("Current position: \(nav.current.label)")
            Text("Previous position: \(nav.previous?.label ?? "—")")
            Divider()
            Text("Legal moves: \(nav.legalMoves.map(\.label).joined(separator: ", "))")
            Text(
                "Tap an adjacent square. Opposite corner takes two taps. " +
                    "Swipe from the left edge or tap the handle to open this drawer."
            )
            .foregroundStyle(Color(white: 0.4))
            Spacer()
        }
        .padding(20)
        .frame(maxHeight: .infinity, alignment: .topLeading)
        .background(Color.white)
        .shadow(radius: drawerOpenShadow)
    }

    private var drawerOpenShadow: CGFloat { 4 }
}

private struct TapGrid: View {
    @ObservedObject var nav: Navigator

    private let cells: [[Cell]] = [
        [Cell(row: .t, col: .l), Cell(row: .t, col: .r)],
        [Cell(row: .b, col: .l), Cell(row: .b, col: .r)],
    ]

    var body: some View {
        VStack(spacing: 6) {
            ForEach(0..<2, id: \.self) { r in
                HStack(spacing: 6) {
                    ForEach(0..<2, id: \.self) { c in
                        let cell = cells[r][c]
                        ZStack {
                            Color.white
                            Text(cell == nav.current ? "X" : "")
                                .font(.system(size: 28))
                                .foregroundStyle(Color(white: 0.13))
                        }
                        .frame(width: 120, height: 120)
                        .overlay(
                            Rectangle().stroke(Color(white: 0.8), lineWidth: 1)
                        )
                        .contentShape(Rectangle())
                        .onTapGesture { nav.tap(cell) }
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
