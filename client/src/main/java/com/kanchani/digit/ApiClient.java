package com.kanchani.digit;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Talks to the Flask REST API. All methods block — call them off the Swing EDT. */
public final class ApiClient {

    /** Thrown for any failure; getMessage() is safe to show to the user. */
    public static class ApiException extends Exception {
        public ApiException(String message) { super(message); }
        public ApiException(String message, Throwable cause) { super(message, cause); }
    }

    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    private String baseUrl;

    public ApiClient(String baseUrl) { setBaseUrl(baseUrl); }

    public void setBaseUrl(String url) {
        String u = url.trim();
        while (u.endsWith("/")) u = u.substring(0, u.length() - 1);
        this.baseUrl = u;
    }

    public String getBaseUrl() { return baseUrl; }

    // ---------------- endpoints ----------------

    /** GET /health -> true if the API reports status "ok". */
    public boolean isHealthy() {
        try {
            HttpResponse<String> r = send(HttpRequest.newBuilder(uri("/health")).GET());
            return r.statusCode() == 200;
        } catch (ApiException e) {
            return false;
        }
    }

    /** POST /predict with a PNG image. */
    public PredictionResult predict(byte[] pngBytes, String filename, String source) throws ApiException {
        String boundary = "----DigitBoundary" + UUID.randomUUID();
        ByteArrayOutputStream body = new ByteArrayOutputStream();
        try {
            part(body, boundary, "source", null, null, source.getBytes(StandardCharsets.UTF_8));
            part(body, boundary, "image", filename, "image/png", pngBytes);
            body.write(("--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new ApiException("Could not build the request.", e);
        }
        HttpRequest.Builder req = HttpRequest.newBuilder(uri("/predict"))
                .header("Content-Type", "multipart/form-data; boundary=" + boundary)
                .POST(HttpRequest.BodyPublishers.ofByteArray(body.toByteArray()));
        return new PredictionResult(call(req));
    }

    /** GET /predictions */
    public List<Prediction> history(int limit) throws ApiException {
        Map<String, Object> j = call(HttpRequest.newBuilder(uri("/predictions?limit=" + limit)).GET());
        List<Prediction> out = new ArrayList<>();
        for (Object o : Json.list(j.get("predictions"))) out.add(Prediction.fromJson(Json.obj(o)));
        return out;
    }

    /** DELETE /predictions/{id} */
    public void delete(int id) throws ApiException {
        call(HttpRequest.newBuilder(uri("/predictions/" + id)).DELETE());
    }

    /** DELETE /predictions */
    public int clearAll() throws ApiException {
        Map<String, Object> j = call(HttpRequest.newBuilder(uri("/predictions")).DELETE());
        return Json.intVal(j.get("deleted_count"), 0);
    }

    /** PATCH /predictions/{id}/feedback */
    public void sendFeedback(int id, int correctedDigit) throws ApiException {
        String json = "{\"corrected_digit\": " + correctedDigit + "}";
        call(HttpRequest.newBuilder(uri("/predictions/" + id + "/feedback"))
                .header("Content-Type", "application/json")
                .method("PATCH", HttpRequest.BodyPublishers.ofString(json)));
    }

    /** GET /predictions/stats -> the "stats" object. */
    public Map<String, Object> stats() throws ApiException {
        return Json.obj(call(HttpRequest.newBuilder(uri("/predictions/stats")).GET()).get("stats"));
    }

    /** GET /predictions/export -> CSV text. */
    public String exportCsv() throws ApiException {
        HttpResponse<String> r = send(HttpRequest.newBuilder(uri("/predictions/export")).GET());
        if (r.statusCode() != 200) throw new ApiException(errorFrom(r));
        return r.body();
    }

    // ---------------- plumbing ----------------

    private URI uri(String path) { return URI.create(baseUrl + path); }

    private Map<String, Object> call(HttpRequest.Builder req) throws ApiException {
        HttpResponse<String> r = send(req);
        if (r.statusCode() < 200 || r.statusCode() >= 300) throw new ApiException(errorFrom(r));
        try {
            return Json.parseObject(r.body());
        } catch (RuntimeException e) {
            throw new ApiException("The server sent an unreadable response.", e);
        }
    }

    private HttpResponse<String> send(HttpRequest.Builder req) throws ApiException {
        try {
            return http.send(req.timeout(Duration.ofSeconds(20)).build(),
                    HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        } catch (java.net.ConnectException e) {
            throw new ApiException("Cannot reach the server at " + baseUrl + ". Is the Flask API running?", e);
        } catch (java.net.http.HttpTimeoutException e) {
            throw new ApiException("The server took too long to respond.", e);
        } catch (IOException e) {
            throw new ApiException("Network error: " + e.getMessage(), e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new ApiException("Request was interrupted.", e);
        }
    }

    private static String errorFrom(HttpResponse<String> r) {
        try {
            String msg = Json.str(Json.parseObject(r.body()).get("error"), null);
            if (msg != null) return msg;
        } catch (RuntimeException ignored) { /* fall through */ }
        return "Server returned HTTP " + r.statusCode() + ".";
    }

    private static void part(ByteArrayOutputStream out, String boundary, String name,
                             String filename, String contentType, byte[] data) throws IOException {
        StringBuilder h = new StringBuilder("--").append(boundary).append("\r\n")
                .append("Content-Disposition: form-data; name=\"").append(name).append('"');
        if (filename != null) h.append("; filename=\"").append(filename).append('"');
        h.append("\r\n");
        if (contentType != null) h.append("Content-Type: ").append(contentType).append("\r\n");
        h.append("\r\n");
        out.write(h.toString().getBytes(StandardCharsets.UTF_8));
        out.write(data);
        out.write("\r\n".getBytes(StandardCharsets.UTF_8));
    }
}
