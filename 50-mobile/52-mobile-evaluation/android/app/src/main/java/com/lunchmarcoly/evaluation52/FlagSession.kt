package com.lunchmarcoly.evaluation52

import android.app.Application
import android.os.Handler
import android.os.Looper
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.launchdarkly.sdk.LDContext
import com.launchdarkly.sdk.android.FeatureFlagChangeListener
import com.launchdarkly.sdk.android.LDClient
import com.launchdarkly.sdk.android.LDConfig

/**
 * LaunchDarkly capability: Android mobile SDK — initialize, string/boolean
 * variation, flag listeners, close.
 * https://launchdarkly.com/docs/sdk/client-side/android
 *
 * Credential is BuildConfig.LD_MOBILE_KEY (from local.properties ld.mobile.key
 * or the LD_MOBILE_KEY env var). Never an SDK key.
 */
class FlagSession {
    var highlight by mutableStateOf("none")
        private set
    var showCount by mutableStateOf(false)
        private set
    var initializeCount by mutableIntStateOf(0)
        private set
    var closeCount by mutableIntStateOf(0)
        private set
    var changeHighlightCount by mutableIntStateOf(0)
        private set
    var changeCountFlagCount by mutableIntStateOf(0)
        private set
    var hasMobileKey by mutableStateOf(false)
        private set
    var status by mutableStateOf("SDK not started")
        private set

    private val main = Handler(Looper.getMainLooper())
    private var client: LDClient? = null

    private val highlightListener = FeatureFlagChangeListener {
        main.post {
            changeHighlightCount += 1
            readFlags()
        }
    }

    private val countListener = FeatureFlagChangeListener {
        main.post {
            changeCountFlagCount += 1
            readFlags()
        }
    }

    fun start(app: Application, username: String) {
        val key = BuildConfig.LD_MOBILE_KEY.trim()
        hasMobileKey = key.isNotEmpty()
        if (key.isEmpty()) {
            highlight = "none"
            showCount = false
            status = "No LD_MOBILE_KEY — serving code defaults"
            return
        }
        status = "Initializing…"
        Thread {
            try {
                val config = LDConfig.Builder(LDConfig.Builder.AutoEnvAttributes.Enabled)
                    .mobileKey(key)
                    .build()
                val context = LDContext.create(username)
                val started = LDClient.init(app, config, context, 5)
                main.post {
                    client = started
                    initializeCount += 1
                    started.registerFeatureFlagListener(HIGHLIGHT_KEY, highlightListener)
                    started.registerFeatureFlagListener(COUNT_KEY, countListener)
                    readFlags()
                    status = "Connected"
                }
            } catch (e: Exception) {
                main.post {
                    highlight = "none"
                    showCount = false
                    status = "Init failed — serving code defaults"
                }
            }
        }.start()
    }

    fun stop() {
        val c = client ?: return
        try {
            c.unregisterFeatureFlagListener(HIGHLIGHT_KEY, highlightListener)
            c.unregisterFeatureFlagListener(COUNT_KEY, countListener)
            c.close()
        } catch (_: Exception) {
        }
        client = null
        closeCount += 1
        highlight = "none"
        showCount = false
        status = "Closed"
    }

    fun sdkLog(): String =
        "initialize ×$initializeCount\n" +
            "change:$HIGHLIGHT_KEY ×$changeHighlightCount\n" +
            "change:$COUNT_KEY ×$changeCountFlagCount\n" +
            "close ×$closeCount"

    private fun readFlags() {
        val c = client ?: return
        highlight = c.stringVariation(HIGHLIGHT_KEY, "none")
        showCount = c.boolVariation(COUNT_KEY, false)
    }

    companion object {
        const val HIGHLIGHT_KEY = "enable-mobile-grid-highlight"
        const val COUNT_KEY = "show-mobile-move-count"
    }
}
