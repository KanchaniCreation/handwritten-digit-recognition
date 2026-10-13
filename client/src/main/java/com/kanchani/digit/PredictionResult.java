package com.kanchani.digit;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Result of POST /predict. */
public final class PredictionResult {
    public final int digit;
    public final double confidence;
    public final Integer id; // null if the server could not save it
    public final List<int[]> topDigits = new ArrayList<>();       // [digit]
    public final List<Double> topConfidences = new ArrayList<>(); // parallel to topDigits

    public PredictionResult(Map<String, Object> m) {
        this.digit = Json.intVal(m.get("predicted_digit"), -1);
        this.confidence = Json.dblVal(m.get("confidence"), 0);
        Object idObj = m.get("id");
        this.id = idObj instanceof Number ? ((Number) idObj).intValue() : null;
        for (Object o : Json.list(m.get("top3"))) {
            Map<String, Object> t = Json.obj(o);
            topDigits.add(new int[]{Json.intVal(t.get("digit"), -1)});
            topConfidences.add(Json.dblVal(t.get("confidence"), 0));
        }
    }
}
