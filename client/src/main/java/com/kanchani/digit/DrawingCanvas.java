package com.kanchani.digit;

import javax.swing.JPanel;
import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Cursor;
import java.awt.Dimension;
import java.awt.Graphics;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.event.MouseAdapter;
import java.awt.event.MouseEvent;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.ArrayDeque;
import java.util.Deque;
import javax.imageio.ImageIO;

/** A square white canvas you draw on with the mouse (black ink). Supports undo. */
public class DrawingCanvas extends JPanel {
    public static final int SIZE = 280; // 10x MNIST, downscaled server-side

    private BufferedImage image = blank();
    private final Deque<BufferedImage> undoStack = new ArrayDeque<>();
    private int brush = 18;
    private int lastX, lastY;
    private boolean dirty = false;
    private Runnable onChange = () -> { };

    public DrawingCanvas() {
        setPreferredSize(new Dimension(SIZE, SIZE));
        setMinimumSize(new Dimension(SIZE, SIZE));
        setCursor(Cursor.getPredefinedCursor(Cursor.CROSSHAIR_CURSOR));
        setBorder(javax.swing.BorderFactory.createLineBorder(new Color(0x888888), 2));

        MouseAdapter m = new MouseAdapter() {
            @Override public void mousePressed(MouseEvent e) {
                pushUndo();
                lastX = e.getX(); lastY = e.getY();
                stroke(lastX, lastY, lastX, lastY);
            }
            @Override public void mouseDragged(MouseEvent e) {
                stroke(lastX, lastY, e.getX(), e.getY());
                lastX = e.getX(); lastY = e.getY();
            }
        };
        addMouseListener(m);
        addMouseMotionListener(m);
    }

    private static BufferedImage blank() {
        BufferedImage img = new BufferedImage(SIZE, SIZE, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = img.createGraphics();
        g.setColor(Color.WHITE);
        g.fillRect(0, 0, SIZE, SIZE);
        g.dispose();
        return img;
    }

    private static BufferedImage copy(BufferedImage src) {
        BufferedImage c = new BufferedImage(SIZE, SIZE, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = c.createGraphics();
        g.drawImage(src, 0, 0, null);
        g.dispose();
        return c;
    }

    private void stroke(int x1, int y1, int x2, int y2) {
        Graphics2D g = image.createGraphics();
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setColor(Color.BLACK);
        g.setStroke(new BasicStroke(brush, BasicStroke.CAP_ROUND, BasicStroke.JOIN_ROUND));
        g.drawLine(x1, y1, x2, y2);
        g.dispose();
        dirty = true;
        repaint();
        onChange.run();
    }

    private void pushUndo() {
        undoStack.push(copy(image));
        while (undoStack.size() > 30) undoStack.removeLast();
    }

    public void clear() {
        pushUndo();
        image = blank();
        dirty = false;
        repaint();
        onChange.run();
    }

    public void undo() {
        if (undoStack.isEmpty()) return;
        image = undoStack.pop();
        dirty = !isBlank(image);
        repaint();
        onChange.run();
    }

    private static boolean isBlank(BufferedImage img) {
        for (int y = 0; y < SIZE; y += 2)
            for (int x = 0; x < SIZE; x += 2)
                if ((img.getRGB(x, y) & 0xFFFFFF) != 0xFFFFFF) return false;
        return true;
    }

    public boolean hasDrawing() { return dirty; }

    public void setBrushSize(int px) { this.brush = Math.max(4, Math.min(40, px)); }

    public void setOnChange(Runnable r) { this.onChange = r == null ? () -> { } : r; }

    public byte[] toPng() throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        ImageIO.write(image, "png", out);
        return out.toByteArray();
    }

    @Override protected void paintComponent(Graphics g) {
        super.paintComponent(g);
        g.drawImage(image, 0, 0, null);
    }
}
