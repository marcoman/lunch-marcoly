package com.lunchmarcoly.evaluation52

import android.app.Application
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { Evaluation52App() }
    }
}

private val CellFill = Color(0xFF2A2A2A)
private val CellStroke = Color(0xFF555555)
private val PageBg = Color(0xFF1A1A1A)
private val Ink = Color(0xFFF0F0F0)
private val Muted = Color(0xFFAAAAAA)

private fun highlightColor(name: String): Color? = when (name) {
    "green" -> Color(0xFF2E7D32)
    "yellow" -> Color(0xFFF9A825)
    "red" -> Color(0xFFC62828)
    "blue" -> Color(0xFF1565C0)
    "purple" -> Color(0xFF6A1B9A)
    else -> null
}

@Composable
fun Evaluation52App() {
    val nav = remember { Navigator() }
    val flags = remember { FlagSession() }
    var loggedIn by remember { mutableStateOf(false) }
    val app = LocalContext.current.applicationContext as Application
    MaterialTheme(colorScheme = darkColorScheme()) {
        Surface(modifier = Modifier.fillMaxSize(), color = PageBg) {
            if (!loggedIn) {
                LoginScreen(
                    onLogin = { name ->
                        if (nav.login(name)) {
                            flags.start(app, name.trim())
                            loggedIn = true
                        }
                    },
                )
            } else {
                GridScreen(
                    nav = nav,
                    flags = flags,
                    onLogout = {
                        flags.stop()
                        nav.logout()
                        loggedIn = false
                    },
                )
            }
        }
    }
}

@Composable
private fun LoginScreen(onLogin: (String) -> Unit) {
    var name by remember { mutableStateOf("") }
    var error by remember { mutableStateOf(false) }
    fun submit() {
        val ok = name.trim().isNotEmpty()
        error = !ok
        if (ok) onLogin(name)
    }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("52-mobile-evaluation[android]", style = MaterialTheme.typography.labelMedium, color = Muted)
        Spacer(Modifier.height(8.dp))
        Text("Login", style = MaterialTheme.typography.headlineSmall, color = Ink)
        Spacer(Modifier.height(12.dp))
        Text(
            "Mobile 2×2 tap lab with LaunchDarkly. Username becomes the context key. " +
                "Enter a username (no password) to continue.",
            color = Muted,
        )
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(
            value = name,
            onValueChange = {
                name = it
                error = false
            },
            label = { Text("Username") },
            singleLine = true,
            isError = error,
            modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = { submit() }),
        )
        if (error) {
            Text("Username is required.", color = Color(0xFFEF9A9A), modifier = Modifier.padding(top = 8.dp))
        }
        Spacer(Modifier.height(16.dp))
        Button(onClick = { submit() }) { Text("Continue") }
    }
}

@Composable
private fun GridScreen(nav: Navigator, flags: FlagSession, onLogout: () -> Unit) {
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val nameColor = highlightColor(flags.highlight) ?: Ink
    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet(modifier = Modifier.fillMaxWidth(0.82f), drawerContainerColor = Color(0xFF222222)) {
                DrawerBody(nav, flags)
            }
        },
    ) {
        Box(Modifier.fillMaxSize()) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(start = 20.dp, end = 16.dp, top = 48.dp, bottom = 16.dp),
            ) {
                Text("52-mobile-evaluation[android]", style = MaterialTheme.typography.labelMedium, color = Muted)
                Text("Name: ${nav.username}", color = nameColor)
                Text("Current position: ${nav.current.label()}", color = Ink)
                Text("Previous position: ${nav.previous?.label() ?: "—"}", color = Ink)
                if (flags.showCount) {
                    Text("Count: ${nav.moveCount}", color = Ink)
                }
                TextButton(onClick = onLogout, modifier = Modifier.align(Alignment.Start)) {
                    Text("Logout")
                }
                Spacer(Modifier.height(12.dp))
                TapGrid(nav, flags.highlight)
            }
            Box(
                modifier = Modifier
                    .align(Alignment.CenterStart)
                    .fillMaxHeight()
                    .width(16.dp)
                    .clickable { scope.launch { drawerState.open() } },
            )
        }
    }
}

@Composable
private fun DrawerBody(nav: Navigator, flags: FlagSession) {
    Column(
        Modifier
            .padding(20.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Text("Lab drawer", style = MaterialTheme.typography.titleMedium, color = Ink)
        Spacer(Modifier.height(8.dp))
        Text("Current position: ${nav.current.label()}", color = Ink)
        Text("Previous position: ${nav.previous?.label() ?: "—"}", color = Ink)
        Text("Legal moves: ${nav.legalMoves().joinToString { it.label() }}", color = Ink)
        Spacer(Modifier.height(8.dp))
        HorizontalDivider()
        Spacer(Modifier.height(8.dp))
        Text("Highlight: ${flags.highlight}", color = Ink)
        Text("Count flag: ${flags.showCount}", color = Ink)
        Text(
            if (flags.hasMobileKey) "Mobile key: present" else "Mobile key: missing",
            color = Muted,
        )
        Text(flags.status, color = Muted)
        Spacer(Modifier.height(8.dp))
        Text("SDK calls", style = MaterialTheme.typography.titleSmall, color = Ink)
        Text(flags.sdkLog(), color = Muted)
        Spacer(Modifier.height(12.dp))
        Text(
            "Tap an adjacent square. Toggle flags in the LaunchDarkly dashboard — " +
                "listeners update this grid without restart.",
            color = Muted,
        )
    }
}

@Composable
private fun TapGrid(nav: Navigator, highlight: String) {
    val cells = listOf(
        listOf(Cell(Row.T, Col.L), Cell(Row.T, Col.R)),
        listOf(Cell(Row.B, Col.L), Cell(Row.B, Col.R)),
    )
    val accent = highlightColor(highlight)
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        cells.forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                row.forEach { cell ->
                    val selected = cell == nav.current
                    val fill = if (selected && accent != null) accent else CellFill
                    Box(
                        modifier = Modifier
                            .width(120.dp)
                            .height(120.dp)
                            .border(1.dp, CellStroke)
                            .clickable { nav.tap(cell) },
                        contentAlignment = Alignment.Center,
                    ) {
                        Surface(color = fill, modifier = Modifier.fillMaxSize()) {
                            Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxSize()) {
                                Text(
                                    text = if (selected) "X" else "",
                                    fontSize = 28.sp,
                                    color = Ink,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
