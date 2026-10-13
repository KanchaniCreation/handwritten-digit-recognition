package com.kanchani.digit;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;

/**
 * Headless check of the client library against a RUNNING API (no GUI needed):
 *   java -cp target/classes com.kanchani.digit.ApiSmokeTest http://localhost:5000 path/to/digit.png
 * Exits non-zero on the first failure.
 */
public class ApiSmokeTest {
    static int checks = 0;

    static void check(boolean cond, String what) {
        checks++;
        if (!cond) { System.err.println("FAIL: " + what); System.exit(1); }
        System.out.println("ok   " + what);
    }

    public static void main(String[] a) throws Exception {
        ApiClient api = new ApiClient(a.length > 0 ? a[0] : "http://localhost:5000");
        byte[] png = Files.readAllBytes(Paths.get(a.length > 1 ? a[1] : "digit.png"));

        check(api.isHealthy(), "health endpoint reports ok");
        api.clearAll();

        PredictionResult r = api.predict(png, "digit.png", "canvas");
        check(r.digit >= 0 && r.digit <= 9, "predict returns a digit 0-9 (" + r.digit + ")");
        check(r.confidence > 0 && r.confidence <= 1, "confidence in (0,1]");
        check(r.topDigits.size() == 3, "top-3 present");
        check(r.id != null, "prediction was saved (id=" + r.id + ")");

        List<Prediction> h = api.history(10);
        check(h.size() == 1 && h.get(0).id == r.id && "canvas".equals(h.get(0).source), "history contains it");

        api.sendFeedback(r.id, 5);
        check(api.history(10).get(0).correctedDigit == 5, "feedback stored");

        Map<String, Object> s = api.stats();
        check(Json.intVal(s.get("total_predictions"), -1) == 1, "stats total = 1");
        check(api.exportCsv().startsWith("id,predicted_digit"), "csv export");

        api.delete(r.id);
        check(api.history(10).isEmpty(), "delete works");
        try { api.delete(r.id); check(false, "deleting twice should fail"); }
        catch (ApiClient.ApiException e) { check(e.getMessage().contains("No prediction"), "404 message surfaced: " + e.getMessage()); }

        try { api.predict("junk".getBytes(), "x.png", "upload"); check(false, "junk image should fail"); }
        catch (ApiClient.ApiException e) { check(true, "bad image rejected: " + e.getMessage()); }

        System.out.println("\nAll " + checks + " checks passed.");
    }
}
