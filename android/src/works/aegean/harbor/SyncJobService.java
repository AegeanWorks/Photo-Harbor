package works.aegean.harbor;

import android.app.job.JobParameters;
import android.app.job.JobService;
import android.content.SharedPreferences;

/** Runs the same sync from JobScheduler, using the settings the activity saved. */
public class SyncJobService extends JobService {
    private Thread worker;

    @Override
    public boolean onStartJob(final JobParameters params) {
        SharedPreferences prefs = getSharedPreferences("harbor", MODE_PRIVATE);
        final String server = prefs.getString("server", "");
        final String key = prefs.getString("key", "");
        final boolean wifi = prefs.getBoolean("wifi", true);
        if (server.isEmpty() || key.isEmpty()) {
            remember("not configured");
            jobFinished(params, false);
            return false;
        }
        worker = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    String report = SyncEngine.sync(SyncJobService.this, server, key, wifi,
                            new SyncEngine.Progress() {
                                @Override
                                public void say(String message) {
                                    // Background runs stay quiet; the next app open shows the result.
                                }
                            });
                    remember(report);
                } catch (Exception error) {
                    String why = error.getMessage() == null ? "unknown error" : error.getMessage();
                    remember("failed: " + why);
                } finally {
                    jobFinished(params, false);
                }
            }
        }, "harbor-background-sync");
        worker.start();
        return true;
    }

    private void remember(String message) {
        getSharedPreferences("harbor", MODE_PRIVATE).edit()
                .putString("last_background", message)
                .putLong("last_background_at", System.currentTimeMillis())
                .apply();
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        if (worker != null) {
            worker.interrupt();
        }
        return true;
    }
}
