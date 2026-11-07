package com.jjustping.tabdeck

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.lifecycle.lifecycleScope
import com.jjustping.tabdeck.data.Deck
import com.jjustping.tabdeck.ui.TabDeckApp

/** TabDeck — native client for a TabDock server (computer at home). */
class MainActivity : ComponentActivity() {
    private lateinit var deck: Deck

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        deck = Deck(applicationContext, lifecycleScope)
        setContent { TabDeckApp(deck) }
        deck.start()
        handle(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    /** QR code / link "http://<ip>:8787/?k=<key>" → pair with that server. */
    private fun handle(i: Intent?) {
        val u: Uri = i?.data ?: return
        val k = u.getQueryParameter("k") ?: return
        if (u.scheme == "http" && !u.host.isNullOrBlank()) deck.pairWithKey("http://${u.host}:${if (u.port > 0) u.port else 8787}", k)
    }

    override fun onResume() { super.onResume(); immersive(); deck.visible = true }
    override fun onPause() { deck.visible = false; super.onPause() }
    override fun onWindowFocusChanged(hasFocus: Boolean) { super.onWindowFocusChanged(hasFocus); if (hasFocus) immersive() }

    private fun immersive() {
        WindowCompat.getInsetsController(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
    }
}
