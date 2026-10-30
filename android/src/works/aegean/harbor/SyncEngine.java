package works.aegean.harbor;

import android.content.ContentResolver;
import android.content.ContentUris;
import android.content.Context;
import android.database.Cursor;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.provider.MediaStore;

import org.json.JSONObject;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneId;

/** Uploads new MediaStore items with the same hash-first protocol as the iPhone Shortcut. */
public final class SyncEngine {
    public interface Progress {
        void say(String message);
    }

    private static final int BUFFER = 64 * 1024;
    private static final Object LOCK = new Object();

    private SyncEngine() {
    }

    public static String sync(Context context, String server, String key, boolean wifiOnly,
                              Progress progress) throws Exception {
        synchronized (LOCK) {
            String base = normalise(server);
            if (wifiOnly && !onWifi(context)) {
                return "Waiting for Wi-Fi. Nothing was sent.";
            }
            JSONObject start = new JSONObject(postJson(base + "/api/sync/start", key, "{}"));
            String since = start.getString("since");
            String startedAt = start.getString("started_at");
            long sinceMillis = parseSince(since);
            progress.say("Looking for new photos since " + since + "…");

            int[] images = syncCollection(context, MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                    base, key, sinceMillis, progress);
            int[] videos = syncCollection(context, MediaStore.Video.Media.EXTERNAL_CONTENT_URI,
                    base, key, sinceMillis, progress);
            int sent = images[0] + videos[0];
            int skipped = images[1] + videos[1];

            postJson(base + "/api/sync/done", key,
                    "{\"started_at\":" + JSONObject.quote(startedAt) + "}");
            return "Done: " + sent + " sent, " + skipped + " already on the PC.";
        }
    }

    private static int[] syncCollection(Context context, Uri collection, String base, String key,
                                        long sinceMillis, Progress progress) throws Exception {
        ContentResolver resolver = context.getContentResolver();
        String[] projection = {"_id", "_display_name", "date_added", "datetaken", "_size"};
        long sinceSeconds = Math.max(sinceMillis / 1000, 0);
        Cursor cursor = resolver.query(collection, projection, "date_added >= ?",
                new String[]{String.valueOf(sinceSeconds)}, "date_added ASC");
        if (cursor == null) {
            return new int[]{0, 0};
        }
        int sent = 0;
        int skipped = 0;
        try {
            int idColumn = cursor.getColumnIndexOrThrow("_id");
            int nameColumn = cursor.getColumnIndexOrThrow("_display_name");
            int addedColumn = cursor.getColumnIndexOrThrow("date_added");
            int takenColumn = cursor.getColumnIndexOrThrow("datetaken");
            int sizeColumn = cursor.getColumnIndexOrThrow("_size");
            while (cursor.moveToNext()) {
                if (Thread.currentThread().isInterrupted()) {
                    throw new InterruptedException("sync stopped");
                }
                long size = cursor.getLong(sizeColumn);
                if (size <= 0) {
                    skipped++;
                    continue;
                }
                String name = cursor.getString(nameColumn);
                if (name == null || name.trim().isEmpty()) {
                    name = "photo";
                }
                long added = cursor.getLong(addedColumn);
                long taken = cursor.getLong(takenColumn);
                if (taken <= 0) {
                    taken = added * 1000L;
                }
                Uri item = ContentUris.withAppendedId(collection, cursor.getLong(idColumn));
                String digest = hash(resolver, item);
                progress.say("Checking " + name + "…");
                if (has(base, key, digest)) {
                    skipped++;
                    continue;
                }
                progress.say("Sending " + name + "…");
                upload(resolver, item, size, name, digest, taken, base, key);
                sent++;
            }
        } finally {
            cursor.close();
        }
        return new int[]{sent, skipped};
    }

    private static String hash(ContentResolver resolver, Uri item) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream input = resolver.openInputStream(item)) {
            if (input == null) {
                throw new IOException("could not open " + item);
            }
            byte[] buffer = new byte[BUFFER];
            int read;
            while ((read = input.read(buffer)) > 0) {
                digest.update(buffer, 0, read);
            }
        }
        StringBuilder hex = new StringBuilder(64);
        for (byte value : digest.digest()) {
            hex.append(String.format("%02x", value & 0xff));
        }
        return hex.toString();
    }

    private static boolean has(String base, String key, String digest) throws Exception {
        JSONObject reply = new JSONObject(get(base + "/api/has?sha256=" + encode(digest), key));
        return "yes".equals(reply.optString("answer"));
    }

    private static void upload(ContentResolver resolver, Uri item, long size, String name,
                               String digest, long taken, String base, String key)
            throws Exception {
        HttpURLConnection connection = open(base + "/api/upload", key, "POST");
        connection.setDoOutput(true);
        connection.setFixedLengthStreamingMode(size);
        connection.setRequestProperty("X-Name", encode(name));
        connection.setRequestProperty("X-Sha256", digest);
        connection.setRequestProperty("X-Taken", Instant.ofEpochMilli(taken).toString());
        try (OutputStream output = connection.getOutputStream();
             InputStream input = resolver.openInputStream(item)) {
            if (input == null) {
                throw new IOException("could not open " + item);
            }
            byte[] buffer = new byte[BUFFER];
            int read;
            while ((read = input.read(buffer)) > 0) {
                output.write(buffer, 0, read);
            }
        }
        read(connection);
    }

    private static String postJson(String url, String key, String body) throws Exception {
        HttpURLConnection connection = open(url, key, "POST");
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        connection.setDoOutput(true);
        connection.setFixedLengthStreamingMode(bytes.length);
        connection.setRequestProperty("Content-Type", "application/json");
        try (OutputStream output = connection.getOutputStream()) {
            output.write(bytes);
        }
        return read(connection);
    }

    private static String get(String url, String key) throws Exception {
        return read(open(url, key, "GET"));
    }

    private static HttpURLConnection open(String url, String key, String method) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(15000);
        connection.setReadTimeout(300000);
        connection.setRequestProperty("X-Harbor-Key", key);
        connection.setRequestProperty("Accept", "application/json");
        return connection;
    }

    private static String read(HttpURLConnection connection) throws Exception {
        int code = connection.getResponseCode();
        InputStream stream = code >= 400 ? connection.getErrorStream() : connection.getInputStream();
        String text = stream == null ? "" : new String(readAll(stream), StandardCharsets.UTF_8);
        if (code < 200 || code >= 300) {
            throw new IOException("Harbor returned " + code + ": " + text);
        }
        return text;
    }

    private static byte[] readAll(InputStream stream) throws IOException {
        try (InputStream input = stream) {
            byte[] buffer = new byte[BUFFER];
            java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
            int read;
            while ((read = input.read(buffer)) > 0) {
                out.write(buffer, 0, read);
            }
            return out.toByteArray();
        }
    }

    private static boolean onWifi(Context context) {
        ConnectivityManager manager =
                (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
        if (manager == null) {
            return false;
        }
        Network network = manager.getActiveNetwork();
        NetworkCapabilities capabilities = manager.getNetworkCapabilities(network);
        return capabilities != null
                && capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI);
    }

    private static long parseSince(String text) {
        try {
            return OffsetDateTime.parse(text).toInstant().toEpochMilli();
        } catch (Exception ignored) {
            try {
                return LocalDateTime.parse(text).atZone(ZoneId.systemDefault())
                        .toInstant().toEpochMilli();
            } catch (Exception alsoIgnored) {
                return 0;
            }
        }
    }

    private static String normalise(String server) {
        String base = server == null ? "" : server.trim();
        if (!base.startsWith("http://") && !base.startsWith("https://")) {
            base = "http://" + base;
        }
        while (base.endsWith("/")) {
            base = base.substring(0, base.length() - 1);
        }
        return base;
    }

    private static String encode(String value) throws Exception {
        return URLEncoder.encode(value, "UTF-8").replace("+", "%20");
    }
}
