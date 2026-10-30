package works.aegean.harbor;

import android.Manifest;
import android.app.Activity;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final int ASK_MEDIA = 41;
    private static final int JOB_ID = 1;

    private EditText server;
    private EditText key;
    private CheckBox wifi;
    private CheckBox background;
    private TextView status;
    private Button syncButton;
    private SharedPreferences prefs;
    private boolean running;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("harbor", MODE_PRIVATE);

        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(20);
        form.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("Harbor");
        title.setTextSize(30);
        form.addView(title);

        TextView intro = new TextView(this);
        intro.setText("Send new photos and videos from this phone to your Harbor PC over home Wi-Fi. "
                + "The PC must be on and Harbor must be running.");
        intro.setTextSize(14);
        intro.setPadding(0, dp(4), 0, dp(14));
        form.addView(intro);

        form.addView(label("Server address"));
        server = new EditText(this);
        server.setHint("http://192.168.1.10:8642");
        server.setSingleLine(true);
        server.setText(prefs.getString("server", ""));
        form.addView(server);

        form.addView(label("Your key"));
        key = new EditText(this);
        key.setHint("Key from the Harbor window");
        key.setSingleLine(true);
        key.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        key.setText(prefs.getString("key", ""));
        form.addView(key);

        wifi = new CheckBox(this);
        wifi.setText("Only sync on Wi-Fi");
        wifi.setChecked(prefs.getBoolean("wifi", true));
        form.addView(wifi);

        background = new CheckBox(this);
        background.setText("Sync every 6 hours in the background");
        background.setChecked(prefs.getBoolean("background", false));
        form.addView(background);

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        buttons.setPadding(0, dp(12), 0, dp(12));

        Button save = new Button(this);
        save.setText("Save");
        save.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                saveSettings(false);
            }
        });
        buttons.addView(save);

        syncButton = new Button(this);
        syncButton.setText("Sync now");
        syncButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View view) {
                saveSettings(true);
            }
        });
        buttons.addView(syncButton);
        form.addView(buttons);

        status = new TextView(this);
        status.setText("Ready.");
        status.setTextSize(14);
        status.setTextIsSelectable(true);
        status.setPadding(0, dp(8), 0, dp(8));
        form.addView(status);

        TextView note = new TextView(this);
        note.setText("The first sync may take a while. Nothing is deleted from the phone. "
                + "Allow photos and videos when Android asks.");
        note.setTextSize(12);
        form.addView(note);

        ScrollView scroll = new ScrollView(this);
        scroll.addView(form);
        setContentView(scroll);

        background.setOnCheckedChangeListener(new android.widget.CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(android.widget.CompoundButton button, boolean checked) {
                saveSettings(false);
                schedule(checked);
            }
        });
        if (background.isChecked()) {
            schedule(true);
        }
    }

    private TextView label(String text) {
        TextView label = new TextView(this);
        label.setText(text);
        label.setTextSize(12);
        label.setPadding(0, dp(10), 0, 0);
        return label;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void saveSettings(boolean syncNow) {
        String address = server.getText().toString().trim();
        String accessKey = key.getText().toString().trim();
        if (address.isEmpty() || accessKey.isEmpty()) {
            status.setText("Enter the server address and your key first.");
            return;
        }
        prefs.edit()
                .putString("server", address)
                .putString("key", accessKey)
                .putBoolean("wifi", wifi.isChecked())
                .putBoolean("background", background.isChecked())
                .apply();
        status.setText("Saved. " + (syncNow ? "Starting sync…" : "Ready."));
        if (syncNow) {
            startSync();
        }
    }

    private void startSync() {
        String permission = Build.VERSION.SDK_INT >= 33
                ? Manifest.permission.READ_MEDIA_IMAGES
                : Manifest.permission.READ_EXTERNAL_STORAGE;
        if (checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED) {
            if (Build.VERSION.SDK_INT >= 33) {
                requestPermissions(new String[]{Manifest.permission.READ_MEDIA_IMAGES,
                        Manifest.permission.READ_MEDIA_VIDEO}, ASK_MEDIA);
            } else {
                requestPermissions(new String[]{permission}, ASK_MEDIA);
            }
            return;
        }
        runSync();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions,
                                           int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode != ASK_MEDIA) {
            return;
        }
        for (int result : results) {
            if (result != PackageManager.PERMISSION_GRANTED) {
                status.setText("Photo access is needed to send new photos.");
                return;
            }
        }
        runSync();
    }

    private void runSync() {
        if (running) {
            return;
        }
        running = true;
        syncButton.setEnabled(false);
        status.setText("Starting…");
        final String address = server.getText().toString().trim();
        final String accessKey = key.getText().toString().trim();
        final boolean wifiOnly = wifi.isChecked();
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    String report = SyncEngine.sync(MainActivity.this, address, accessKey,
                            wifiOnly, new SyncEngine.Progress() {
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
                    show("Sync failed: " + error.getMessage());
                } finally {
                    running = false;
                    runOnUiThread(new Runnable() {
                        @Override
                        public void run() {
                            syncButton.setEnabled(true);
                        }
                    });
                }
            }
        }, "harbor-sync").start();
    }

    private void show(final String message) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                status.setText(message);
            }
        });
    }

    private void schedule(boolean enabled) {
        JobScheduler scheduler = (JobScheduler) getSystemService(JOB_SCHEDULER_SERVICE);
        if (scheduler == null) {
            return;
        }
        if (!enabled) {
            scheduler.cancel(JOB_ID);
            return;
        }
        JobInfo.Builder builder = new JobInfo.Builder(JOB_ID,
                new ComponentName(this, SyncJobService.class))
                .setRequiredNetworkType(wifi.isChecked()
                        ? JobInfo.NETWORK_TYPE_UNMETERED : JobInfo.NETWORK_TYPE_ANY)
                .setPersisted(true)
                .setPeriodic(6L * 60L * 60L * 1000L);
        if (scheduler.schedule(builder.build()) != JobScheduler.RESULT_SUCCESS) {
            status.setText("Android refused the background schedule.");
        }
    }
}
