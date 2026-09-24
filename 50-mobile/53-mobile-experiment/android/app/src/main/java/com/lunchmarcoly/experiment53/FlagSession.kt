package com.lunchmarcoly.experiment53

import android.app.Application
import android.os.Handler
import android.os.Looper
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.launchdarkly.sdk.LDContext
import com.launchdarkly.sdk.android.LDClient
import com.launchdarkly.sdk.android.LDConfig

/**
 * Runs one LaunchDarkly Experimentation session for a stable user context.
 *
 * The boolean variation call records experiment exposure; the custom event
 * records conversion after the first valid move.
 * https://launchdarkly.com/docs/sdk/features/experimentation
 * https://launchdarkly.com/docs/sdk/client-side/android
 */
class FlagSession {
    var treatment by mutableStateOf(false)
        private set
    var ready by mutableStateOf(false)
        private set
    var exposureEvaluated by mutableStateOf(false)
        private set
    var conversionSent by mutableStateOf(false)
        private set
    var hasMobileKey by mutableStateOf(false)
        private set
    var status by mutableStateOf("SDK not started")
        private set
    var initializeCount by mutableIntStateOf(0)
        private set
    var evaluationCount by mutableIntStateOf(0)
        private set
    var trackCount by mutableIntStateOf(0)
        private set
    var closeCount by mutableIntStateOf(0)
        private set

    private val main = Handler(Looper.getMainLooper())
    private var client: LDClient? = null

    /**
     * Builds the context before SDK initialization so evaluation and tracking
     * share one identity. Context attributes support experiment result analysis.
     * https://launchdarkly.com/docs/home/observability/contexts
     */
    fun start(app: Application, username: String) {
        stopClient(countClose = false)
        treatment = false
        ready = false
        exposureEvaluated = false
        conversionSent = false

        val stableKey = username.trim()
        val context = LDContext.builder(stableKey)
            .set("platform", PLATFORM)
            .set("app-version", APP_VERSION)
            .build()
        val key = BuildConfig.LD_MOBILE_KEY.trim()
        hasMobileKey = key.isNotEmpty()
        if (key.isEmpty()) {
            status = "No LD_MOBILE_KEY — serving control fallback"
            ready = true
            return
        }

        status = "Initializing…"
        Thread {
            try {
                val config = LDConfig.Builder(LDConfig.Builder.AutoEnvAttributes.Enabled)
                    .mobileKey(key)
                    .build()
                val started = LDClient.init(app, config, context, 5)
                val servedTreatment = started.boolVariation(FLAG_KEY, false)
                main.post {
                    client = started
                    initializeCount += 1
                    evaluationCount += 1
                    treatment = servedTreatment
                    exposureEvaluated = true
                    ready = true
                    status = "Connected; experiment exposure evaluated"
                }
            } catch (_: Exception) {
                main.post {
                    treatment = false
                    ready = true
                    status = "Init failed — serving control fallback"
                }
            }
        }.start()
    }

    /**
     * Sends the Experimentation custom conversion event at most once per login.
     * https://launchdarkly.com/docs/home/experimentation/events
     */
    fun trackCompletion() {
        if (conversionSent) return
        val activeClient = client ?: return
        activeClient.track(CONVERSION_EVENT)
        conversionSent = true
        trackCount += 1
    }

    fun stop() {
        stopClient(countClose = true)
        treatment = false
        ready = false
        exposureEvaluated = false
        conversionSent = false
        status = "Closed"
    }

    fun sdkLog(): String =
        "initialize ×$initializeCount\n" +
            "variation:$FLAG_KEY ×$evaluationCount\n" +
            "track:$CONVERSION_EVENT ×$trackCount\n" +
            "close ×$closeCount"

    private fun stopClient(countClose: Boolean) {
        val activeClient = client ?: return
        try {
            activeClient.close()
        } catch (_: Exception) {
        }
        client = null
        if (countClose) closeCount += 1
    }

    companion object {
        const val FLAG_KEY = "acme-mobile-onboarding-v2"
        const val CONVERSION_EVENT = "mobile_onboarding_completed"
        const val PLATFORM = "android"
        const val APP_VERSION = "1.0.0"
    }
}
