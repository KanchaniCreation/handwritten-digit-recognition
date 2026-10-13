package com.kanchani.digit;

import java.util.Map;

/** One row of prediction history, as returned by the API. */
public final class Prediction {
    public final int id;
    public final int predictedDigit;
    public final double confidence;
    public final Integer correctedDigit; // null = no feedback yet
    public final String source;
    public final String createdAt;

    public Prediction(int id, int predictedDigit, double confidence, Integer correctedDigit,
                      String source, String createdAt) {
        this.id = id;
        this.predictedDigit = predictedDigit;
        this.confidence = confidence;
        this.correctedDigit = correctedDigit;
        this.source = source;
        this.createdAt = createdAt;
    }

    public static Prediction fromJson(Map<String, Object> m) {
        Object corrected = m.get("corrected_digit");
        return new Prediction(
                Json.intVal(m.get("id"), -1),
                Json.intVal(m.get("predicted_digit"), -1),
                Json.dblVal(m.get("confidence"), 0),
                corrected instanceof Number ? ((Number) corrected).intValue() : null,
                Json.str(m.get("source"), ""),
                Json.str(m.get("created_at"), ""));
    }
}
