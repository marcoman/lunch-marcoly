package com.lunchmarcoly.reference51

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
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
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
import androidx.compose.material3.lightColorScheme
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
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { Reference51App() }
    }
}

private val CellFill = Color.White
private val CellStroke = Color(0xFFCCCCCC)
private val PageBg = Color(0xFFFAFAFA)
private val Ink = Color(0xFF222222)

@Composable
fun Reference51App() {
    val nav = remember { Navigator() }
    var loggedIn by remember { mutableStateOf(false) }
    MaterialTheme(colorScheme = lightColorScheme()) {
        Surface(modifier = Modifier.fillMaxSize(), color = PageBg) {
            if (!loggedIn) {
                LoginScreen(
                    onLogin = { name ->
                        if (nav.login(name)) loggedIn = true
                    },
                )
            } else {
                GridScreen(
                    nav = nav,
                    onLogout = {
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
        Text("51-reference[android]", style = MaterialTheme.typography.labelMedium, color = Color(0xFF666666))
        Spacer(Modifier.height(8.dp))
        Text("Login", style = MaterialTheme.typography.headlineSmall, color = Ink)
        Spacer(Modifier.height(12.dp))
        Text(
            "This is the mobile 2×2 tap lab. It is not the web WASD grid. " +
                "Enter a username (no password) to continue.",
            color = Color(0xFF666666),
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
            Text("Username is required.", color = Color(0xFFC62828), modifier = Modifier.padding(top = 8.dp))
        }
        Spacer(Modifier.height(16.dp))
        Button(onClick = { submit() }) { Text("Continue") }
    }
}

@Composable
private fun GridScreen(nav: Navigator, onLogout: () -> Unit) {
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet(modifier = Modifier.fillMaxWidth(0.78f)) {
                DrawerBody(nav)
            }
        },
    ) {
        Box(Modifier.fillMaxSize()) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(start = 20.dp, end = 16.dp, top = 48.dp, bottom = 16.dp),
            ) {
                Text("51-reference[android]", style = MaterialTheme.typography.labelMedium, color = Color(0xFF666666))
                Text("Name: ${nav.username}", color = Ink)
                Text("Current position: ${nav.current.label()}", color = Ink)
                Text("Previous position: ${nav.previous?.label() ?: "—"}", color = Ink)
                TextButton(onClick = onLogout, modifier = Modifier.align(Alignment.Start)) {
                    Text("Logout")
                }
                Spacer(Modifier.height(12.dp))
                TapGrid(nav)
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
private fun DrawerBody(nav: Navigator) {
    Column(Modifier.padding(20.dp)) {
        Text("Lab drawer", style = MaterialTheme.typography.titleMedium, color = Ink)
        Spacer(Modifier.height(8.dp))
        Text("Current position: ${nav.current.label()}", color = Ink)
        Text("Previous position: ${nav.previous?.label() ?: "—"}", color = Ink)
        Spacer(Modifier.height(8.dp))
        HorizontalDivider()
        Spacer(Modifier.height(8.dp))
        Text(
            "Legal moves: ${nav.legalMoves().joinToString { it.label() }}",
            color = Ink,
        )
        Spacer(Modifier.height(12.dp))
        Text(
            "Tap an adjacent square. Opposite corner takes two taps. " +
                "Swipe from the left edge or tap the handle to open this drawer.",
            color = Color(0xFF666666),
        )
    }
}

@Composable
private fun TapGrid(nav: Navigator) {
    val cells = listOf(
        listOf(Cell(Row.T, Col.L), Cell(Row.T, Col.R)),
        listOf(Cell(Row.B, Col.L), Cell(Row.B, Col.R)),
    )
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        cells.forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                row.forEach { cell ->
                    val selected = cell == nav.current
                    Box(
                        modifier = Modifier
                            .width(120.dp)
                            .height(120.dp)
                            .border(1.dp, CellStroke)
                            .clickable { nav.tap(cell) },
                        contentAlignment = Alignment.Center,
                    ) {
                        Surface(color = CellFill, modifier = Modifier.fillMaxSize()) {
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
