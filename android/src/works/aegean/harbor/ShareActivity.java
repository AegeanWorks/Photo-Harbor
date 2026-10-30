package works.aegean.harbor;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;

/** Receives photos and videos from the Android share sheet and uploads them immediately. */
public class ShareActivity extends Activity {
    private TextView status;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        int pad = Math.round(20 * getResources().getDisplayMetrics().density);
        form.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("Send to Harbor");
        title.setTextSize(26);
        form.addView(title);

        status = new TextView(this);
        status.setText("Preparing…");
        status.setTextSize(14);
        status.setTextIsSelectable(true);
        status.setPadding(0, pad / 2, 0, pad / 2);
        form.addView(status);

        Button open = new Button(this);
        open.setText("Open Harbor");
        open.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                startActivity(new Intent(ShareActivity.this, MainActivity.class));
                finish();
            }
        });
        form.addView(open);
        setContentView(form);

        SharedPreferences prefs = getSharedPreferences("harbor", MODE_PRIVATE);
        final String server = prefs.getString("server", "");
        final String key = prefs.getString("key", "");
        final ArrayList<Uri> uris = sharedUris(getIntent());
        if (uris.isEmpty()) {
            status.setText("Nothing to send.");
            return;
        }
        if (server.isEmpty() || key.isEmpty()) {
            status.setText("Open Harbor first and save the server address and your key.");
            return;
        }
        status.setText("Sending " + uris.size() + " item" + (uris.size() == 1 ? "" : "s") + "…");
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    String report = SyncEngine.share(ShareActivity.this, uris, server, key,
                            new SyncEngine.Progress() {
                                @Override
                                public void say(final String message) {
                                    runOnUiThread(new Runnable() {
                                        @Override
                                        public void run() {
                                            status.setText(message);
                                        }
                                    });
                                }
                            });
                    show(report);
                } catch (final Exception error) {
                    show("Send failed: " + error.getMessage());
                }
            }
        }, "harbor-share").start();
    }

    private ArrayList<Uri> sharedUris(Intent intent) {
        ArrayList<Uri> uris = new ArrayList<>();
        if (intent == null) {
            return uris;
        }
        String action = intent.getAction();
        if (Intent.ACTION_SEND.equals(action)) {
            Uri uri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (uri != null) {
                uris.add(uri);
            }
        } else if (Intent.ACTION_SEND_MULTIPLE.equals(action)) {
            ArrayList<Uri> list = intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if (list != null) {
                uris.addAll(list);
            }
        }
        if (uris.isEmpty() && intent.getClipData() != null) {
            ClipData clip = intent.getClipData();
            for (int index = 0; index < clip.getItemCount(); index++) {
                Uri uri = clip.getItemAt(index).getUri();
                if (uri != null) {
                    uris.add(uri);
                }
            }
        }
        return uris;
    }

    private void show(final String message) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                status.setText(message);
            }
        });
    }

}
