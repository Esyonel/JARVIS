package com.jarvis.remote;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.PermissionRequest;
import android.webkit.SslErrorHandler;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * JARVIS Remote — a thin native wrapper around JARVIS's own web dashboard
 * (dashboard/server.py + dashboard/static/app.html), which already provides
 * mic streaming, chat, and file upload over a LAN WebSocket connection.
 *
 * This app does not reimplement any of that; it just hosts the same page in
 * a WebView with the permissions (mic) and quirks (self-signed HTTPS cert on
 * a private LAN IP) that a plain browser tab would otherwise need manual
 * steps for, so it behaves like a real installed app.
 */
public class MainActivity extends Activity {

    private static final String PREFS = "jarvis_remote";
    private static final String KEY_URL = "server_url";
    private static final int REQ_MIC = 1001;
    private static final int REQ_FILE_CHOOSER = 1002;

    private WebView webView;
    private ValueCallback<Uri[]> filePathCallback;

    private LinearLayout setupScreen;
    private FrameLayout webScreen;
    private TextView urlBar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor("#00060a"));

        setupScreen = buildSetupScreen();
        webScreen = buildWebScreen();

        root.addView(setupScreen);
        root.addView(webScreen);
        setContentView(root);

        requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQ_MIC);

        String saved = prefs().getString(KEY_URL, null);
        if (saved != null && !saved.isEmpty()) {
            showWeb(saved);
        } else {
            showSetup();
        }
    }

    private SharedPreferences prefs() {
        return getSharedPreferences(PREFS, MODE_PRIVATE);
    }

    // ── Setup screen: enter the JARVIS dashboard URL once ──────────────────

    private LinearLayout buildSetupScreen() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setPadding(48, 48, 48, 48);
        box.setBackgroundColor(Color.parseColor("#00060a"));

        TextView title = new TextView(this);
        title.setText("JARVIS'e Bağlan");
        title.setTextColor(Color.parseColor("#00d4ff"));
        title.setTextSize(22);
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, 0, 0, 24);

        TextView hint = new TextView(this);
        hint.setText("JARVIS penceresinde \"REMOTE CONTROL\" butonuna basıp "
                + "gösterilen adresi (örn. https://192.168.1.20:47291) aşağıya yaz. "
                + "Telefon, bilgisayarla aynı Wi-Fi ağında olmalı.");
        hint.setTextColor(Color.parseColor("#8ffcff"));
        hint.setTextSize(13);
        hint.setGravity(Gravity.CENTER);
        hint.setPadding(0, 0, 0, 32);

        final EditText input = new EditText(this);
        input.setHint("https://192.168.x.x:47291");
        input.setHintTextColor(Color.parseColor("#3a8a9a"));
        input.setTextColor(Color.WHITE);
        input.setSingleLine(true);

        Button connect = new Button(this);
        connect.setText("Bağlan");
        connect.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String url = input.getText().toString().trim();
                if (!url.isEmpty()) {
                    if (!url.startsWith("http")) url = "https://" + url;
                    prefs().edit().putString(KEY_URL, url).apply();
                    showWeb(url);
                }
            }
        });

        box.addView(title);
        box.addView(hint);
        box.addView(input, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        box.addView(connect);
        return box;
    }

    private void showSetup() {
        setupScreen.setVisibility(View.VISIBLE);
        webScreen.setVisibility(View.GONE);
    }

    // ── Web screen: thin top bar (change server) + full WebView ────────────

    private FrameLayout buildWebScreen() {
        FrameLayout frame = new FrameLayout(this);
        frame.setVisibility(View.GONE);

        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);

        LinearLayout topBar = new LinearLayout(this);
        topBar.setOrientation(LinearLayout.HORIZONTAL);
        topBar.setBackgroundColor(Color.parseColor("#010d14"));
        topBar.setGravity(Gravity.CENTER_VERTICAL);
        topBar.setPadding(16, 8, 16, 8);

        urlBar = new TextView(this);
        urlBar.setTextColor(Color.parseColor("#3a8a9a"));
        urlBar.setTextSize(11);
        urlBar.setSingleLine(true);

        Button change = new Button(this);
        change.setText("Sunucu Değiştir");
        change.setTextSize(10);
        change.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                prefs().edit().remove(KEY_URL).apply();
                showSetup();
            }
        });

        LinearLayout.LayoutParams urlParams = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        topBar.addView(urlBar, urlParams);
        topBar.addView(change);

        webView = new WebView(this);
        webView.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                // The dashboard's cert is self-signed for a private LAN IP (the
                // user's own PC, generated by JARVIS itself) — no public CA
                // will ever validate that, so it's trusted here deliberately,
                // the same trust decision a desktop browser's "proceed anyway"
                // click makes.
                handler.proceed();
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        request.grant(request.getResources());
                    }
                });
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                              FileChooserParams params) {
                filePathCallback = callback;
                Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                startActivityForResult(Intent.createChooser(intent, "Dosya seç"), REQ_FILE_CHOOSER);
                return true;
            }
        });

        column.addView(topBar);
        column.addView(webView);
        frame.addView(column);
        return frame;
    }

    private void showWeb(String url) {
        setupScreen.setVisibility(View.GONE);
        webScreen.setVisibility(View.VISIBLE);
        urlBar.setText(url);
        webView.loadUrl(url);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_FILE_CHOOSER) {
            if (filePathCallback == null) return;
            Uri[] results = null;
            if (resultCode == Activity.RESULT_OK && data != null && data.getData() != null) {
                results = new Uri[]{data.getData()};
            }
            filePathCallback.onReceiveValue(results);
            filePathCallback = null;
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        // Nothing to do — the WebView's own onPermissionRequest handles mic
        // access for the page; this is just the OS-level app permission.
    }

    @Override
    public void onBackPressed() {
        if (webScreen.getVisibility() == View.VISIBLE && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
