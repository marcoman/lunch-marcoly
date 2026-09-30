package com.lunchmarcoly.rollout54

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
 * Mobile SDK session for a platform-staggered release.
 * The device sends platform=android. A targeting rule decides the variation.
 * https://launchdarkly.com/docs/home/flags/target-with-rules
 * https://launchdarkly.com/docs/sdk/client-side/android
 */
class FlagSession {
    var released by mutableStateOf(false)
        private set
    var initializeCount by mutableIntStateOf(0)
        private set
    var closeCount by mutableIntStateOf(0)
        private set
    var changeCount by mutableIntStateOf(0)
        private set
    var trackCount by mutableIntStateOf(0)
        private set
    var hasMobileKey by mutableStateOf(false)
        private set
    var status by mutableStateOf("SDK not started")
        private set

    private val main = Handler(Looper.getMainLooper())
    private var client: LDClient? = null
    private var moveTracked = false

    private val rolloutListener = FeatureFlagChangeListener {
        main.post {
            changeCount += 1
            readFlag()
        }
    }

    /**
     * Build the user context, including platform, before init.
     * https://launchdarkly.com/docs/home/observability/contexts
     */
    fun start(app: Application, username: String) {
        stopClient(countClose = false)
        released = false
        moveTracked = false
        val key = BuildConfig.LD_MOBILE_KEY.trim()
        hasMobileKey = key.isNotEmpty()
        if (key.isEmpty()) {
            status = "No LD_MOBILE_KEY — serving the previous experience"
            return
        }
        status = "Initializing…"
        val context = LDContext.builder(username)
            .set("platform", PLATFORM)
            .build()
        Thread {
            try {
                val config = LDConfig.Builder(LDConfig.Builder.AutoEnvAttributes.Enabled)
                    .mobileKey(key)
                    .build()
                val started = LDClient.init(app, config, context, 5)
                main.post {
                    client = started
                    initializeCount += 1
                    started.registerFeatureFlagListener(FLAG_KEY, rolloutListener)
                    readFlag()
                    status = "Connected · platform=$PLATFORM"
                }
            } catch (_: Exception) {
                main.post {
                    released = false
                    status = "Init failed — serving the previous experience"
                }
            }
        }.start()
    }

    /**
     * One custom event per login, after a real cell change.
     * https://launchdarkly.com/docs/sdk/features/events
     */
    fun trackMove() {
        if (moveTracked) return
        val active = client ?: return
        active.track(EVENT_KEY)
        moveTracked = true
        trackCount += 1
    }

    fun stop() {
        stopClient(countClose = true)
        released = false
        moveTracked = false
        status = "Closed"
    }

    fun sdkLog(): String =
        "initialize ×$initializeCount\n" +
            "change:$FLAG_KEY ×$changeCount\n" +
            "track:$EVENT_KEY ×$trackCount\n" +
            "close ×$closeCount"

    private fun readFlag() {
        val active = client ?: return
        released = active.boolVariation(FLAG_KEY, false)
    }

    private fun stopClient(countClose: Boolean) {
        val active = client ?: return
        try {
            active.unregisterFeatureFlagListener(FLAG_KEY, rolloutListener)
            active.close()
        } catch (_: Exception) {
        }
        client = null
        if (countClose) closeCount += 1
    }

    companion object {
        const val FLAG_KEY = "enable-mobile-platform-rollout"
        const val EVENT_KEY = "mobile_platform_rollout_move"
        const val PLATFORM = "android"
    }
}
