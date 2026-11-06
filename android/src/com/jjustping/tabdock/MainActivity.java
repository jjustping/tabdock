package com.jjustping.tabdock;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import org.json.JSONArray;
import org.json.JSONObject;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.ArrayDeque;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * TabDock tablet client: a fullscreen WebView that keeps the screen on and finds TabDock
 * servers on the LAN by itself via Bonjour/NSD (_tabdock._tcp), which a browser cannot do.
 */
public class MainActivity extends Activity {
    private static final String START = "file:///android_asset/start.html";
    private static final String SERVICE = "_tabdock._tcp";

    private WebView web;
    private SharedPreferences prefs;
    private NsdManager nsd;
    private NsdManager.DiscoveryListener discovery;
    private WifiManager.MulticastLock mcLock;
    private final Map<String, String> found = Collections.synchronizedMap(new LinkedHashMap<String, String>());
    private final ArrayDeque<NsdServiceInfo> toResolve = new ArrayDeque<>();
    private boolean resolving = false;
    private final Handler ui = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("tabdock", MODE_PRIVATE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        web = new WebView(this);
        web.setBackgroundColor(0xFF0A0C0F);
        setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setTextZoom(100);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(true);
        s.setAllowUniversalAccessFromFileURLs(true); // start page probes http://<lan-ip>/api/hello
        s.setUserAgentString(s.getUserAgentString() + " TabDockApp/" + versionName());
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true);
        web.addJavascriptInterface(new Bridge(), "TabDockNative");
        web.setWebChromeClient(new WebChromeClient());
        web.setWebViewClient(new Client());

        startDiscovery();
        handleIntent(getIntent(), true);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleIntent(intent, false);
    }

    /** Intent data "http://ip:port/?k=TOKEN" opens that server directly (used for pairing via adb/QR). */
    private void handleIntent(Intent intent, boolean first) {
        Uri data = intent != null ? intent.getData() : null;
        if (data != null && "http".equals(data.getScheme())) {
            web.loadUrl(data.toString());
        } else if (first) {
            web.loadUrl(START);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        immersive();
        web.onResume();
    }

    @Override
    protected void onPause() {
        CookieManager.getInstance().flush();
        web.onPause();
        super.onPause();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) immersive();
    }

    @SuppressWarnings("deprecation")
    private void immersive() {
        if (Build.VERSION.SDK_INT >= 30) {
            WindowInsetsController c = getWindow().getInsetsController();
            if (c != null) {
                c.hide(WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars());
                c.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        }
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else if (!START.equals(web.getUrl())) web.loadUrl(START + "#menu");
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        try { if (discovery != null) nsd.stopServiceDiscovery(discovery); } catch (Exception ignored) { }
        if (mcLock != null && mcLock.isHeld()) mcLock.release();
        super.onDestroy();
    }

    // ---------------- web client ----------------
    private class Client extends WebViewClient {
        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
            Uri u = req.getUrl();
            String scheme = u.getScheme();
            if ("file".equals(scheme)) return false;
            if ("http".equals(scheme) && isLocalHost(u.getHost())) return false; // TabDock itself
            // wfolio galleries, docs links, etc. -> the normal browser
            try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) { }
            return true;
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            Uri u = Uri.parse(url);
            if ("http".equals(u.getScheme()) && isLocalHost(u.getHost())) {
                String base = "http://" + u.getHost() + (u.getPort() > 0 ? ":" + u.getPort() : "");
                prefs.edit().putString("last", base).apply();
                CookieManager.getInstance().flush(); // keep the sign-in cookie across restarts
            }
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
            if (req.isForMainFrame() && !req.getUrl().toString().startsWith("file:")) {
                view.loadUrl(START + "#lost");
            }
        }
    }

    private String versionName() {
        try { return getPackageManager().getPackageInfo(getPackageName(), 0).versionName; }
        catch (Exception e) { return "0"; }
    }

    private static boolean isLocalHost(String h) {
        if (h == null) return false;
        return h.startsWith("192.168.") || h.startsWith("10.") || h.matches("^172\\.(1[6-9]|2\\d|3[01])\\..*")
                || h.endsWith(".local") || h.equals("localhost");
    }

    // ---------------- Bonjour / NSD ----------------
    private void startDiscovery() {
        try {
            WifiManager wm = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            if (wm != null) {
                mcLock = wm.createMulticastLock("tabdock");
                mcLock.setReferenceCounted(false);
                mcLock.acquire();
            }
            nsd = (NsdManager) getSystemService(Context.NSD_SERVICE);
            discovery = new NsdManager.DiscoveryListener() {
                public void onStartDiscoveryFailed(String t, int e) { }
                public void onStopDiscoveryFailed(String t, int e) { }
                public void onDiscoveryStarted(String t) { }
                public void onDiscoveryStopped(String t) { }
                public void onServiceFound(NsdServiceInfo info) { queueResolve(info); }
                public void onServiceLost(NsdServiceInfo info) { }
            };
            nsd.discoverServices(SERVICE, NsdManager.PROTOCOL_DNS_SD, discovery);
        } catch (Exception ignored) { }
    }

    private synchronized void queueResolve(NsdServiceInfo info) {
        toResolve.add(info);
        if (!resolving) resolveNext();
    }

    @SuppressWarnings("deprecation")
    private synchronized void resolveNext() {
        final NsdServiceInfo next = toResolve.poll();
        if (next == null) { resolving = false; return; }
        resolving = true;
        nsd.resolveService(next, new NsdManager.ResolveListener() {
            public void onResolveFailed(NsdServiceInfo i, int e) {
                ui.postDelayed(() -> resolveNext(), 300);
            }
            public void onServiceResolved(NsdServiceInfo i) {
                InetAddress a = i.getHost();
                if (a instanceof Inet4Address) {
                    found.put(i.getServiceName(), "http://" + a.getHostAddress() + ":" + i.getPort());
                }
                ui.post(() -> resolveNext());
            }
        });
    }

    private static String deviceIp() {
        try {
            for (NetworkInterface ni : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!ni.isUp() || ni.isLoopback()) continue;
                for (InetAddress a : Collections.list(ni.getInetAddresses())) {
                    if (a instanceof Inet4Address && a.isSiteLocalAddress()) return a.getHostAddress();
                }
            }
        } catch (Exception ignored) { }
        return "";
    }

    // ---------------- JS bridge for start.html ----------------
    private class Bridge {
        @JavascriptInterface
        public String servers() {
            JSONArray arr = new JSONArray();
            synchronized (found) {
                for (Map.Entry<String, String> e : found.entrySet()) {
                    try {
                        arr.put(new JSONObject().put("name", e.getKey()).put("base", e.getValue()));
                    } catch (Exception ignored) { }
                }
            }
            return arr.toString();
        }

        @JavascriptInterface
        public String saved() { return prefs.getString("last", ""); }

        @JavascriptInterface
        public void forget() { prefs.edit().remove("last").apply(); }

        @JavascriptInterface
        public String deviceIp() { return MainActivity.deviceIp(); }

        @JavascriptInterface
        public String version() {
            try { return getPackageManager().getPackageInfo(getPackageName(), 0).versionName; }
            catch (Exception e) { return "?"; }
        }
    }
}
