package com.kanchani.digit;

import javax.swing.JPanel;
import java.awt.Color;
import java.awt.Dimension;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.RenderingHints;

/** Shows the predicted digit in large type, plus a confidence bar and the top-3 candidates. */
public class ResultPanel extends JPanel {
    private PredictionResult result;
    private String message = "Draw a digit and press Predict";

    public ResultPanel() {
        setPreferredSize(new Dimension(300, 280));
        setBackground(Color.WHITE);
        setBorder(javax.swing.BorderFactory.createLineBorder(new Color(0xCCCCCC)));
    }

    public void showResult(PredictionResult r) { this.result = r; repaint(); }

    public void showMessage(String m) { this.result = null; this.message = m; repaint(); }

    @Override protected void paintComponent(Graphics g0) {
        super.paintComponent(g0);
        Graphics2D g = (Graphics2D) g0;
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
        int w = getWidth();

        if (result == null) {
            g.setColor(Color.GRAY);
            g.setFont(getFont().deriveFont(Font.PLAIN, 14f));
            FontMetrics fm = g.getFontMetrics();
            g.drawString(message, Math.max(8, (w - fm.stringWidth(message)) / 2), getHeight() / 2);
            return;
        }

        // big digit
        g.setFont(getFont().deriveFont(Font.BOLD, 96f));
        FontMetrics fm = g.getFontMetrics();
        String d = String.valueOf(result.digit);
        g.setColor(confidenceColor(result.confidence));
        g.drawString(d, (w - fm.stringWidth(d)) / 2, 100);

        // confidence
        g.setFont(getFont().deriveFont(Font.PLAIN, 14f));
        g.setColor(Color.DARK_GRAY);
        String conf = String.format("Confidence: %.1f%%", result.confidence * 100);
        g.drawString(conf, (w - g.getFontMetrics().stringWidth(conf)) / 2, 128);
        bar(g, 20, 138, w - 40, 12, result.confidence, confidenceColor(result.confidence));

        // low-confidence hint
        if (result.confidence < 0.7) {
            g.setColor(new Color(0xB45309));
            String hint = "Not very sure — try drawing it bigger/clearer";
            g.setFont(getFont().deriveFont(Font.ITALIC, 12f));
            g.drawString(hint, (w - g.getFontMetrics().stringWidth(hint)) / 2, 168);
        }

        // top 3
        g.setFont(getFont().deriveFont(Font.BOLD, 12f));
        g.setColor(Color.DARK_GRAY);
        g.drawString("Top guesses", 20, 195);
        g.setFont(getFont().deriveFont(Font.PLAIN, 13f));
        for (int i = 0; i < result.topDigits.size() && i < 3; i++) {
            int y = 215 + i * 22;
            double c = result.topConfidences.get(i);
            g.setColor(Color.BLACK);
            g.drawString(String.valueOf(result.topDigits.get(i)[0]), 20, y + 11);
            bar(g, 40, y, w - 110, 12, c, new Color(0x3B82F6));
            g.setColor(Color.DARK_GRAY);
            g.drawString(String.format("%.1f%%", c * 100), w - 62, y + 11);
        }
    }

    private static void bar(Graphics2D g, int x, int y, int w, int h, double frac, Color c) {
        g.setColor(new Color(0xE5E7EB));
        g.fillRoundRect(x, y, w, h, h, h);
        g.setColor(c);
        g.fillRoundRect(x, y, (int) Math.max(h, w * Math.max(0, Math.min(1, frac))), h, h, h);
    }

    private static Color confidenceColor(double c) {
        if (c >= 0.9) return new Color(0x15803D);
        if (c >= 0.7) return new Color(0xCA8A04);
        return new Color(0xDC2626);
    }
}
