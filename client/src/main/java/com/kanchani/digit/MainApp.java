package com.kanchani.digit;

import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.awt.event.KeyEvent;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.function.Consumer;

/**
 * Handwritten Digit Recognition — Java Swing client.
 *
 * Draw a digit (or open an image), click Predict, and the picture is sent to the
 * Flask REST API, which runs the TensorFlow model and stores the result in PostgreSQL.
 * The History tab shows saved predictions; the Stats tab charts them.
 */
public class MainApp extends JFrame {

    private static final String DEFAULT_URL = System.getProperty("api.url",
            System.getenv("DIGIT_API_URL") != null ? System.getenv("DIGIT_API_URL") : "http://localhost:5000");
    private static final DateTimeFormatter TIME_FMT = DateTimeFormatter.ofPattern("dd MMM yyyy HH:mm:ss");

    private final ApiClient api = new ApiClient(DEFAULT_URL);

    private final DrawingCanvas canvas = new DrawingCanvas();
    private final ResultPanel resultPanel = new ResultPanel();
    private final JButton predictBtn = new JButton("Predict");
    private final JLabel status = new JLabel(" ");
    private final JLabel health = new JLabel("●");
    private final JTextField urlField = new JTextField(DEFAULT_URL, 22);

    private final DefaultTableModel historyModel = new DefaultTableModel(
            new Object[]{"ID", "Digit", "Confidence", "Corrected", "Source", "When"}, 0) {
        @Override public boolean isCellEditable(int r, int c) { return false; }
    };
    private final JTable historyTable = new JTable(historyModel);
    private final StatsPanel statsPanel = new StatsPanel();

    private PredictionResult lastResult;

    public MainApp() {
        super("Handwritten Digit Recognition");
        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setLayout(new BorderLayout(8, 8));
        ((JComponent) getContentPane()).setBorder(BorderFactory.createEmptyBorder(8, 8, 8, 8));

        add(buildTopBar(), BorderLayout.NORTH);

        JTabbedPane tabs = new JTabbedPane();
        tabs.addTab("Draw", buildDrawTab());
        tabs.addTab("History", buildHistoryTab());
        tabs.addTab("Stats", buildStatsTab());
        tabs.addChangeListener(e -> {
            if (tabs.getSelectedIndex() == 1) refreshHistory();
            if (tabs.getSelectedIndex() == 2) refreshStats();
        });
        add(tabs, BorderLayout.CENTER);

        status.setBorder(BorderFactory.createEmptyBorder(2, 4, 2, 4));
        add(status, BorderLayout.SOUTH);

        pack();
        setMinimumSize(getSize());
        setLocationRelativeTo(null);
        checkHealth();
    }

    // ------------------------------------------------------------------ UI

    private JPanel buildTopBar() {
        JPanel p = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 0));
        p.add(new JLabel("API URL:"));
        p.add(urlField);
        JButton connect = new JButton("Connect");
        connect.addActionListener(e -> { api.setBaseUrl(urlField.getText()); checkHealth(); });
        p.add(connect);
        health.setFont(health.getFont().deriveFont(18f));
        health.setForeground(Color.GRAY);
        p.add(health);
        return p;
    }

    private JPanel buildDrawTab() {
        JPanel root = new JPanel(new BorderLayout(12, 12));
        root.setBorder(BorderFactory.createEmptyBorder(8, 8, 8, 8));

        JPanel left = new JPanel(new BorderLayout(0, 8));
        // Keep the canvas at its fixed 280x280 size (don't let BorderLayout stretch it).
        JPanel canvasHolder = new JPanel(new GridBagLayout());
        canvasHolder.add(canvas);
        left.add(canvasHolder, BorderLayout.CENTER);

        JPanel brushRow = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 0));
        brushRow.add(new JLabel("Brush:"));
        JSlider brush = new JSlider(6, 36, 18);
        brush.addChangeListener(e -> canvas.setBrushSize(brush.getValue()));
        brushRow.add(brush);

        JPanel buttons = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 0));
        predictBtn.addActionListener(e -> predictFromCanvas());
        JButton clear = new JButton("Clear");
        clear.addActionListener(e -> { canvas.clear(); resultPanel.showMessage("Draw a digit and press Predict"); });
        JButton undo = new JButton("Undo");
        undo.addActionListener(e -> canvas.undo());
        JButton open = new JButton("Open image…");
        open.addActionListener(e -> predictFromFile());
        buttons.add(predictBtn);
        buttons.add(undo);
        buttons.add(clear);
        buttons.add(open);

        JPanel south = new JPanel(new GridLayout(2, 1, 0, 4));
        south.add(brushRow);
        south.add(buttons);
        left.add(south, BorderLayout.SOUTH);

        JPanel right = new JPanel(new BorderLayout(0, 8));
        right.add(resultPanel, BorderLayout.CENTER);
        JButton wrong = new JButton("Wrong? Correct this digit…");
        wrong.addActionListener(e -> correctLastResult());
        right.add(wrong, BorderLayout.SOUTH);

        root.add(left, BorderLayout.WEST);
        root.add(right, BorderLayout.CENTER);

        // keyboard shortcuts: Enter = predict, Esc = clear, Ctrl+Z = undo
        InputMap im = root.getInputMap(JComponent.WHEN_IN_FOCUSED_WINDOW);
        ActionMap am = root.getActionMap();
        im.put(KeyStroke.getKeyStroke(KeyEvent.VK_ENTER, 0), "predict");
        im.put(KeyStroke.getKeyStroke(KeyEvent.VK_ESCAPE, 0), "clear");
        im.put(KeyStroke.getKeyStroke(KeyEvent.VK_Z, Toolkit.getDefaultToolkit().getMenuShortcutKeyMaskEx()), "undo");
        am.put("predict", new AbstractAction() { public void actionPerformed(java.awt.event.ActionEvent e) { predictFromCanvas(); } });
        am.put("clear", new AbstractAction() { public void actionPerformed(java.awt.event.ActionEvent e) { clear.doClick(); } });
        am.put("undo", new AbstractAction() { public void actionPerformed(java.awt.event.ActionEvent e) { canvas.undo(); } });
        return root;
    }

    private JPanel buildHistoryTab() {
        JPanel p = new JPanel(new BorderLayout(6, 6));
        p.setBorder(BorderFactory.createEmptyBorder(8, 8, 8, 8));
        historyTable.setAutoCreateRowSorter(true);
        historyTable.setSelectionMode(ListSelectionModel.SINGLE_SELECTION);
        historyTable.setRowHeight(24);
        p.add(new JScrollPane(historyTable), BorderLayout.CENTER);

        JPanel bar = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 0));
        JButton refresh = new JButton("Refresh");
        refresh.addActionListener(e -> refreshHistory());
        JButton correct = new JButton("Correct digit…");
        correct.addActionListener(e -> correctSelected());
        JButton del = new JButton("Delete selected");
        del.addActionListener(e -> deleteSelected());
        JButton clearAll = new JButton("Clear all");
        clearAll.addActionListener(e -> clearAllHistory());
        JButton export = new JButton("Export CSV…");
        export.addActionListener(e -> exportCsv());
        for (JButton b : new JButton[]{refresh, correct, del, clearAll, export}) bar.add(b);
        p.add(bar, BorderLayout.SOUTH);
        return p;
    }

    private JPanel buildStatsTab() {
        JPanel p = new JPanel(new BorderLayout(6, 6));
        p.setBorder(BorderFactory.createEmptyBorder(8, 8, 8, 8));
        p.add(statsPanel, BorderLayout.CENTER);
        JButton refresh = new JButton("Refresh");
        refresh.addActionListener(e -> refreshStats());
        JPanel bar = new JPanel(new FlowLayout(FlowLayout.LEFT));
        bar.add(refresh);
        p.add(bar, BorderLayout.SOUTH);
        return p;
    }

    // ------------------------------------------------------------------ actions

    private void predictFromCanvas() {
        if (!canvas.hasDrawing()) { setStatus("Draw a digit first.", true); return; }
        byte[] png;
        try { png = canvas.toPng(); }
        catch (IOException ex) { setStatus("Could not capture the drawing.", true); return; }
        runPredict(png, "canvas.png", "canvas");
    }

    private void predictFromFile() {
        JFileChooser fc = new JFileChooser();
        fc.setFileFilter(new javax.swing.filechooser.FileNameExtensionFilter(
                "Images (png, jpg, bmp)", "png", "jpg", "jpeg", "bmp"));
        if (fc.showOpenDialog(this) != JFileChooser.APPROVE_OPTION) return;
        File f = fc.getSelectedFile();
        try {
            runPredict(Files.readAllBytes(f.toPath()), f.getName(), "upload");
        } catch (IOException ex) {
            setStatus("Could not read " + f.getName(), true);
        }
    }

    private void runPredict(byte[] image, String name, String source) {
        predictBtn.setEnabled(false);
        setStatus("Predicting…", false);
        background(() -> api.predict(image, name, source), r -> {
            predictBtn.setEnabled(true);
            lastResult = r;
            resultPanel.showResult(r);
            setStatus(r.id == null
                    ? "Predicted " + r.digit + " (but the server could not save it to the database)."
                    : "Predicted " + r.digit + " — saved as #" + r.id + ".", r.id == null);
            health.setForeground(new Color(0x15803D));
        }, ex -> {
            predictBtn.setEnabled(true);
            resultPanel.showMessage("No result");
            setStatus(ex.getMessage(), true);
        });
    }

    private void correctLastResult() {
        if (lastResult == null || lastResult.id == null) { setStatus("No saved prediction to correct yet.", true); return; }
        askCorrection(lastResult.id, lastResult.digit);
    }

    private void correctSelected() {
        Integer id = selectedId();
        if (id == null) { setStatus("Select a row first.", true); return; }
        int row = historyTable.convertRowIndexToModel(historyTable.getSelectedRow());
        askCorrection(id, (Integer) historyModel.getValueAt(row, 1));
    }

    private void askCorrection(int id, int predicted) {
        Integer[] digits = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9};
        Object pick = JOptionPane.showInputDialog(this,
                "Prediction #" + id + " said " + predicted + ".\nWhat digit was it really?",
                "Correct digit", JOptionPane.QUESTION_MESSAGE, null, digits, predicted);
        if (pick == null) return;
        int corrected = (Integer) pick;
        background(() -> { api.sendFeedback(id, corrected); return null; },
                v -> { setStatus("Thanks — saved correction for #" + id + ".", false); refreshHistory(); },
                ex -> setStatus(ex.getMessage(), true));
    }

    private void refreshHistory() {
        background(() -> api.history(200), this::fillHistory, ex -> setStatus(ex.getMessage(), true));
    }

    private void fillHistory(List<Prediction> rows) {
        historyModel.setRowCount(0);
        for (Prediction p : rows) {
            historyModel.addRow(new Object[]{p.id, p.predictedDigit,
                    String.format("%.1f%%", p.confidence * 100),
                    p.correctedDigit == null ? "—" : p.correctedDigit,
                    p.source, prettyTime(p.createdAt)});
        }
        setStatus(rows.size() + " prediction(s) in history.", false);
    }

    private void deleteSelected() {
        Integer id = selectedId();
        if (id == null) { setStatus("Select a row first.", true); return; }
        background(() -> { api.delete(id); return null; },
                v -> { setStatus("Deleted #" + id + ".", false); refreshHistory(); },
                ex -> setStatus(ex.getMessage(), true));
    }

    private void clearAllHistory() {
        if (JOptionPane.showConfirmDialog(this, "Delete ALL saved predictions? This cannot be undone.",
                "Clear history", JOptionPane.OK_CANCEL_OPTION, JOptionPane.WARNING_MESSAGE) != JOptionPane.OK_OPTION) return;
        background(api::clearAll,
                n -> { setStatus("Deleted " + n + " prediction(s).", false); refreshHistory(); },
                ex -> setStatus(ex.getMessage(), true));
    }

    private void exportCsv() {
        JFileChooser fc = new JFileChooser();
        fc.setSelectedFile(new File("predictions.csv"));
        if (fc.showSaveDialog(this) != JFileChooser.APPROVE_OPTION) return;
        File out = fc.getSelectedFile();
        background(api::exportCsv, csv -> {
            try {
                Files.write(out.toPath(), csv.getBytes(StandardCharsets.UTF_8));
                setStatus("Exported to " + out.getAbsolutePath(), false);
            } catch (IOException e) {
                setStatus("Could not write " + out.getName() + ": " + e.getMessage(), true);
            }
        }, ex -> setStatus(ex.getMessage(), true));
    }

    private void refreshStats() {
        background(api::stats, statsPanel::showStats, ex -> { statsPanel.showMessage(ex.getMessage()); setStatus(ex.getMessage(), true); });
    }

    private void checkHealth() {
        new SwingWorker<Boolean, Void>() {
            @Override protected Boolean doInBackground() { return api.isHealthy(); }
            @Override protected void done() {
                boolean ok;
                try { ok = get(); } catch (Exception e) { ok = false; }
                health.setForeground(ok ? new Color(0x15803D) : new Color(0xDC2626));
                health.setToolTipText(ok ? "API healthy" : "API unreachable or degraded");
                setStatus(ok ? "Connected to " + api.getBaseUrl() : "Cannot reach a healthy API at " + api.getBaseUrl(), !ok);
            }
        }.execute();
    }

    // ------------------------------------------------------------------ helpers

    private Integer selectedId() {
        int r = historyTable.getSelectedRow();
        if (r < 0) return null;
        return (Integer) historyModel.getValueAt(historyTable.convertRowIndexToModel(r), 0);
    }

    private static String prettyTime(String iso) {
        try {
            return OffsetDateTime.parse(iso).atZoneSameInstant(ZoneId.systemDefault()).format(TIME_FMT);
        } catch (RuntimeException e) {
            return iso;
        }
    }

    private void setStatus(String msg, boolean error) {
        status.setText(msg);
        status.setForeground(error ? new Color(0xB91C1C) : Color.DARK_GRAY);
    }

    /** Runs work off the Swing thread, then delivers the result (or ApiException) back on it. */
    private <T> void background(Callable<T> work, Consumer<T> ok, Consumer<ApiClient.ApiException> fail) {
        new SwingWorker<T, Void>() {
            @Override protected T doInBackground() throws Exception { return work.call(); }
            @Override protected void done() {
                try {
                    ok.accept(get());
                } catch (java.util.concurrent.ExecutionException e) {
                    Throwable c = e.getCause();
                    fail.accept(c instanceof ApiClient.ApiException
                            ? (ApiClient.ApiException) c
                            : new ApiClient.ApiException("Unexpected error: " + c));
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }
        }.execute();
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> {
            try { UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName()); } catch (Exception ignored) { }
            new MainApp().setVisible(true);
        });
    }
}
