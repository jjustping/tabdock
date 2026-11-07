package com.jjustping.tabdeck

import android.content.Intent
import android.net.Uri
import android.content.pm.PackageManager
import android.os.Build
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
private const val LAN = "android.permission.ACCESS_LOCAL_NETWORK"

class MainActivity : ComponentActivity() {
    private lateinit var deck: Deck

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        deck = Deck(applicationContext, lifecycleScope)
        setContent { TabDeckApp(deck) }
        // Android 17+: talking to computers on the home network is a runtime permission. Without it the system
        // asks to pick a device on every launch; with it discovery and the connection just work.
        if (Build.VERSION.SDK_INT >= 37 && checkSelfPermission(LAN) != PackageManager.PERMISSION_GRANTED) requestPermissions(arrayOf(LAN), 7)
        else deck.start()
        handle(intent)
    }

    override fun onRequestPermissionsResult(code: Int, perms: Array<out String>, res: IntArray) {
        super.onRequestPermissionsResult(code, perms, res)
        if (code == 7) deck.start()
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
