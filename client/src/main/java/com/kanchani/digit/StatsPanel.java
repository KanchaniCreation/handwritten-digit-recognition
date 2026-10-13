package com.kanchani.digit;

import javax.swing.JPanel;
import java.awt.Color;
import java.awt.Dimension;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.util.Map;

/** Bar chart of how often each digit was predicted, plus headline numbers. */
public class StatsPanel extends JPanel {
    private int total;
    private double avgConfidence;
    private Double feedbackAccuracy;
    private int reviewed;
    private final int[] counts = new int[10];
    private String message = "Press Refresh to load statistics";

    public StatsPanel() {
        setBackground(Color.WHITE);
        setPreferredSize(new Dimension(400, 300));
    }

    public void showMessage(String m) { total = -1; message = m; repaint(); }

    public void showStats(Map<String, Object> s) {
        total = Json.intVal(s.get("total_predictions"), 0);
        avgConfidence = Json.dblVal(s.get("average_confidence"), 0);
        reviewed = Json.intVal(s.get("reviewed_predictions"), 0);
        Object fa = s.get("feedback_accuracy");
        feedbackAccuracy = fa instanceof Number ? ((Number) fa).doubleValue() : null;
        Map<String, Object> dc = Json.obj(s.get("digit_counts"));
        for (int d = 0; d < 10; d++) counts[d] = dc == null ? 0 : Json.intVal(dc.get(String.valueOf(d)), 0);
        repaint();
    }

    @Override protected void paintComponent(Graphics g0) {
        super.paintComponent(g0);
        Graphics2D g = (Graphics2D) g0;
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
        int w = getWidth(), h = getHeight();

        if (total < 0) {
            g.setColor(Color.GRAY);
            g.setFont(getFont().deriveFont(14f));
            g.drawString(message, 20, 40);
            return;
        }

        g.setColor(Color.DARK_GRAY);
        g.setFont(getFont().deriveFont(Font.BOLD, 14f));
        g.drawString("Total predictions: " + total, 20, 28);
        g.drawString(String.format("Average confidence: %.1f%%", avgConfidence * 100), 20, 50);
        String fb = feedbackAccuracy == null
                ? "Feedback accuracy: n/a (use 'Correct digit…' in History)"
                : String.format("Feedback accuracy: %.1f%% (%d reviewed)", feedbackAccuracy * 100, reviewed);
        g.drawString(fb, 20, 72);

        int left = 40, right = w - 20, top = 100, bottom = h - 40;
        int max = 1;
        for (int c : counts) max = Math.max(max, c);
        int slot = (right - left) / 10;
        int barW = Math.max(10, slot - 12);
        g.setFont(getFont().deriveFont(Font.PLAIN, 12f));
        FontMetrics fm = g.getFontMetrics();
        g.setColor(new Color(0xD1D5DB));
        g.drawLine(left, bottom, right, bottom);
        for (int d = 0; d < 10; d++) {
            int x = left + d * slot + (slot - barW) / 2;
            int bh = (int) ((bottom - top) * (counts[d] / (double) max));
            g.setColor(new Color(0x3B82F6));
            g.fillRoundRect(x, bottom - bh, barW, bh, 6, 6);
            g.setColor(Color.DARK_GRAY);
            String lbl = String.valueOf(d);
            g.drawString(lbl, x + (barW - fm.stringWidth(lbl)) / 2, bottom + 16);
            String cnt = String.valueOf(counts[d]);
            g.drawString(cnt, x + (barW - fm.stringWidth(cnt)) / 2, bottom - bh - 4);
        }
        g.drawString("Predictions per digit", left, h - 8);
    }
}
