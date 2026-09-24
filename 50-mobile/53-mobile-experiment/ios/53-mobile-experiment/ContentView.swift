import SwiftUI

struct ContentView: View {
    private enum Destination {
        case login
        case loading
        case helper
        case grid
    }

    @StateObject private var nav = Navigator()
    @StateObject private var experiment = ExperimentSession()
    @State private var destination: Destination = .login
    @State private var drawerOpen = false

    var body: some View {
        Group {
            switch destination {
            case .login:
                LoginScreen(onLogin: login)
            case .loading:
                LoadingScreen()
            case .helper:
                HowToPlayScreen(
                    onContinue: { destination = .grid },
                    onLogout: logout
                )
            case .grid:
                GridScreen(
                    nav: nav,
                    experiment: experiment,
                    drawerOpen: $drawerOpen,
                    onLogout: logout
                )
            }
        }
        .preferredColorScheme(.dark)
    }

    private func login(_ name: String) {
        guard nav.login(name) else { return }
        destination = .loading
        experiment.start(username: nav.username) {
            destination = experiment.variation ? .helper : .grid
        }
    }

    private func logout() {
        experiment.stop()
        nav.logout()
        drawerOpen = false
        destination = .login
    }
}

private struct Banner: View {
    var body: some View {
        Text("53-mobile-experiment[ios]")
            .font(.caption)
            .foregroundStyle(Color(white: 0.65))
    }
}

private struct LoginScreen: View {
    var onLogin: (String) -> Void
    @State private var name = ""
    @State private var error = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Banner()
            Text("Login")
                .font(.title2)
            Text("Username becomes the stable LaunchDarkly context key.")
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
        .screenStyle()
    }

    private func submit() {
        let valid = !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        error = !valid
        if valid { onLogin(name) }
    }
}

private struct LoadingScreen: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Banner()
            ProgressView("Evaluating experiment…")
            Spacer()
        }
        .screenStyle()
    }
}

private struct HowToPlayScreen: View {
    var onContinue: () -> Void
    var onLogout: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Banner()
            VStack(alignment: .leading, spacing: 10) {
                Text("How to play")
                    .font(.title2)
                    .bold()
                Text("Tap a square next to X. Your first successful move completes onboarding.")
                Button("Continue", action: onContinue)
                    .buttonStyle(.borderedProminent)
            }
            .padding(20)
            .background(Color(white: 0.16))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            Button("Logout", action: onLogout)
            Spacer()
        }
        .screenStyle()
    }
}

private struct GridScreen: View {
    @ObservedObject var nav: Navigator
    @ObservedObject var experiment: ExperimentSession
    @Binding var drawerOpen: Bool
    var onLogout: () -> Void

    var body: some View {
        ZStack(alignment: .leading) {
            VStack(alignment: .leading, spacing: 8) {
                Banner()
                Text("Name: \(nav.username)")
                Text("Current position: \(nav.current.label)")
                Text("Previous position: \(nav.previous?.label ?? "—")")
                Text("Count: \(nav.moveCount)")
                Button("Logout", action: onLogout)
                TapGrid(nav: nav) { successful in
                    if successful {
                        experiment.trackCompletedMove()
                    }
                }
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

            LabDrawer(nav: nav, experiment: experiment)
                .frame(width: 320)
                .offset(x: drawerOpen ? 0 : -320)
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
    @ObservedObject var experiment: ExperimentSession

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                Text("Lab drawer")
                    .font(.headline)
                Text("Variation: \(experiment.variation.description)")
                Text("Platform: ios")
                Text("Exposure: \(experiment.exposureEvaluated ? "evaluated" : "not evaluated")")
                Text("Conversion: \(experiment.conversionSent ? "sent" : "not sent")")
                Divider()
                Text("Flag key")
                    .font(.subheadline)
                Text(ExperimentSession.flagKey)
                    .foregroundStyle(Color(white: 0.65))
                Text(experiment.hasMobileKey ? "Mobile key: present" : "Mobile key: missing")
                    .foregroundStyle(Color(white: 0.65))
                Text("Status: \(experiment.status)")
                    .foregroundStyle(Color(white: 0.65))
                Divider()
                Text("Current position: \(nav.current.label)")
                Text("Previous position: \(nav.previous?.label ?? "—")")
                Text("Legal moves: \(nav.legalMoves.map(\.label).joined(separator: ", "))")
                Text("SDK calls")
                    .font(.subheadline)
                Text(experiment.sdkLog)
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
    var onTap: (Bool) -> Void

    private let cells = [
        [Cell(row: .t, col: .l), Cell(row: .t, col: .r)],
        [Cell(row: .b, col: .l), Cell(row: .b, col: .r)],
    ]

    var body: some View {
        VStack(spacing: 6) {
            ForEach(0..<2, id: \.self) { row in
                HStack(spacing: 6) {
                    ForEach(0..<2, id: \.self) { column in
                        let cell = cells[row][column]
                        let selected = cell == nav.current
                        ZStack {
                            Color(white: 0.18)
                            Text(selected ? "X" : "")
                                .font(.system(size: 28))
                        }
                        .frame(width: 120, height: 120)
                        .overlay(Rectangle().stroke(Color(white: 0.35), lineWidth: 1))
                        .contentShape(Rectangle())
                        .onTapGesture { onTap(nav.tap(cell)) }
                    }
                }
            }
        }
        .padding(.top, 8)
    }
}

private extension View {
    func screenStyle() -> some View {
        padding(24)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .background(Color(white: 0.1))
    }
}

#Preview {
    ContentView()
}
