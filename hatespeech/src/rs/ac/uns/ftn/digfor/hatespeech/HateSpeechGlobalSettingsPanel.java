package rs.ac.uns.ftn.digfor.hatespeech;

import java.awt.BorderLayout;
import java.awt.Dimension;
import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;
import javax.swing.GroupLayout;
import javax.swing.JButton;
import javax.swing.JCheckBox;
import javax.swing.JComboBox;
import javax.swing.JFileChooser;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JProgressBar;
import javax.swing.JScrollPane;
import javax.swing.JSlider;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.SwingWorker;
import org.openide.awt.Mnemonics;
import org.sleuthkit.autopsy.ingest.IngestMessage;
import org.sleuthkit.autopsy.ingest.IngestServices;
import org.sleuthkit.autopsy.ingest.IngestModuleGlobalSettingsPanel;

@SuppressWarnings("PMD.SingularField")
public class HateSpeechGlobalSettingsPanel extends IngestModuleGlobalSettingsPanel {
    private static final int CONTENT_WIDTH = 520;
    private static final int DEFAULT_TIMEOUT_SECONDS = 900;

    private JLabel titleLabel;
    private JLabel modelsDirLabel;
    private JTextArea modelsDirHelpTextArea;
    private JTextField modelsDirField;
    private JButton browseButton;
    private JLabel timeoutLabel;
    private JCheckBox timeoutEnabledCheckBox;
    private JLabel timeoutSecondsLabel;
    private JTextField timeoutSecondsField;
    private JLabel logPathLabel;
    private JLabel logFileLabel;
    private JTextField logFileField;
    private JButton browseLogFileButton;
    private JLabel evaluationFileLabel;
    private JTextField evaluationFileField;
    private JButton browseEvaluationFileButton;
    private JButton downloadButton;
    private JButton checkButton;
    private JProgressBar downloadProgressBar;
    private JLabel extendedSettingsLabel;
    private JTextArea batchSizeHelpTextArea;
    private JLabel batchSizeLabel;
    private JComboBox<Integer> batchSizeComboBox;
    private JTextArea maxSeqLengthHelpTextArea;
    private JLabel maxSeqLengthLabel;
    private JComboBox<Integer> maxSeqLengthComboBox;
    private JTextArea hateThresholdHelpTextArea;
    private JLabel hateThresholdLabel;
    private JSlider hateThresholdSlider;
    private JLabel hateThresholdValueLabel;
    private JCheckBox useCudaCheckBox;
    private JTextArea useCudaHelpTextArea;
    private JLabel hateLabelIdsLabel;
    private JTextField hateLabelIdsField;
    private JLabel hateLabelNamesLabel;
    private JTextField hateLabelNamesField;
    private JTextArea hateLabelsHelpTextArea;
    private JTextArea statusTextArea;
    private JScrollPane statusScrollPane;

    HateSpeechGlobalSettingsPanel() {
        initComponents();
        modelsDirField.setText(HateSpeechGlobalSettings.getModelsDirectory());
        timeoutEnabledCheckBox.setSelected(HateSpeechGlobalSettings.isTimeoutEnabled());
        timeoutSecondsField.setText(Integer.toString(HateSpeechGlobalSettings.getTimeoutSeconds()));
        logFileField.setText(HateSpeechGlobalSettings.getLogFilePattern());
        evaluationFileField.setText(HateSpeechGlobalSettings.getEvaluationFilePattern());
        batchSizeComboBox.setSelectedItem(HateSpeechGlobalSettings.getBatchSize());
        maxSeqLengthComboBox.setSelectedItem(HateSpeechGlobalSettings.getMaxSeqLength());
        hateThresholdSlider.setValue((int) Math.round(HateSpeechGlobalSettings.getHateThreshold() * 100.0));
        updateHateThresholdLabel();
        useCudaCheckBox.setSelected(HateSpeechGlobalSettings.useCuda());
        hateLabelIdsField.setText(HateSpeechGlobalSettings.getHateLabelIds());
        hateLabelNamesField.setText(HateSpeechGlobalSettings.getHateLabelNames());
        updateTimeoutEnabledState();
    }

    @Override
    public void saveSettings() {
        HateSpeechGlobalSettings.setModelsDirectory(modelsDirField.getText());
        HateSpeechGlobalSettings.setLogFilePattern(logFileField.getText());
        HateSpeechGlobalSettings.setEvaluationFilePattern(evaluationFileField.getText());
        HateSpeechGlobalSettings.setTimeoutEnabled(timeoutEnabledCheckBox.isSelected());
        HateSpeechGlobalSettings.setTimeoutSeconds(parseTimeoutSeconds());
        HateSpeechGlobalSettings.setBatchSize(selectedInteger(batchSizeComboBox, 32));
        HateSpeechGlobalSettings.setMaxSeqLength(selectedInteger(maxSeqLengthComboBox, 512));
        HateSpeechGlobalSettings.setHateThreshold(hateThresholdSlider.getValue() / 100.0);
        HateSpeechGlobalSettings.setUseCuda(useCudaCheckBox.isSelected());
        HateSpeechGlobalSettings.setHateLabelIds(hateLabelIdsField.getText());
        HateSpeechGlobalSettings.setHateLabelNames(hateLabelNamesField.getText());
    }

    private void initComponents() {
        titleLabel = new JLabel();
        modelsDirLabel = new JLabel();
        modelsDirHelpTextArea = new JTextArea();
        modelsDirField = new JTextField();
        browseButton = new JButton();
        timeoutLabel = new JLabel();
        timeoutEnabledCheckBox = new JCheckBox();
        timeoutSecondsLabel = new JLabel();
        timeoutSecondsField = new JTextField();
        logPathLabel = new JLabel();
        logFileLabel = new JLabel();
        logFileField = new JTextField();
        browseLogFileButton = new JButton();
        evaluationFileLabel = new JLabel();
        evaluationFileField = new JTextField();
        browseEvaluationFileButton = new JButton();
        downloadButton = new JButton();
        checkButton = new JButton();
        downloadProgressBar = new JProgressBar();
        extendedSettingsLabel = new JLabel();
        batchSizeHelpTextArea = new JTextArea();
        batchSizeLabel = new JLabel();
        batchSizeComboBox = new JComboBox<>(new Integer[]{1, 8, 32});
        maxSeqLengthHelpTextArea = new JTextArea();
        maxSeqLengthLabel = new JLabel();
        maxSeqLengthComboBox = new JComboBox<>(new Integer[]{64, 128, 256, 512});
        hateThresholdHelpTextArea = new JTextArea();
        hateThresholdLabel = new JLabel();
        hateThresholdSlider = new JSlider(0, 100, 50);
        hateThresholdValueLabel = new JLabel();
        useCudaCheckBox = new JCheckBox();
        useCudaHelpTextArea = new JTextArea();
        hateLabelIdsLabel = new JLabel();
        hateLabelIdsField = new JTextField();
        hateLabelNamesLabel = new JLabel();
        hateLabelNamesField = new JTextField();
        hateLabelsHelpTextArea = new JTextArea();
        statusTextArea = new JTextArea();
        statusScrollPane = new JScrollPane();

        Mnemonics.setLocalizedText(titleLabel, "<html><b>Hate Speech Detector Global Settings</b></html>");
        Mnemonics.setLocalizedText(modelsDirLabel, "Local models folder");
        Mnemonics.setLocalizedText(browseButton, "Browse...");
        Mnemonics.setLocalizedText(timeoutLabel, "<html><b>Limit model execution time</b></html>");
        Mnemonics.setLocalizedText(timeoutEnabledCheckBox, "Enable timeout for model execution");
        Mnemonics.setLocalizedText(timeoutSecondsLabel, "Timeout (seconds)");
        Mnemonics.setLocalizedText(logPathLabel, "<html><b>Log file location</b></html>");
        Mnemonics.setLocalizedText(logFileLabel, "Log file");
        Mnemonics.setLocalizedText(browseLogFileButton, "Browse...");
        Mnemonics.setLocalizedText(evaluationFileLabel, "Evaluation CSV");
        Mnemonics.setLocalizedText(browseEvaluationFileButton, "Browse...");
        Mnemonics.setLocalizedText(downloadButton, "Download models");
        Mnemonics.setLocalizedText(checkButton, "Check models");
        Mnemonics.setLocalizedText(extendedSettingsLabel, "<html><b>Extended model settings</b></html>");
        Mnemonics.setLocalizedText(batchSizeLabel, "Batch size");
        Mnemonics.setLocalizedText(maxSeqLengthLabel, "Max sequence length");
        Mnemonics.setLocalizedText(hateThresholdLabel, "Hate threshold");
        Mnemonics.setLocalizedText(useCudaCheckBox, "Use CUDA when available");
        Mnemonics.setLocalizedText(hateLabelIdsLabel, "Hate label IDs");
        Mnemonics.setLocalizedText(hateLabelNamesLabel, "Hate label names");
        downloadProgressBar.setIndeterminate(true);
        downloadProgressBar.setVisible(false);
        downloadProgressBar.setStringPainted(true);
        downloadProgressBar.setString("Downloading models...");

        modelsDirHelpTextArea.setEditable(false);
        modelsDirHelpTextArea.setLineWrap(true);
        modelsDirHelpTextArea.setWrapStyleWord(true);
        modelsDirHelpTextArea.setRows(3);
        modelsDirHelpTextArea.setOpaque(false);
        modelsDirHelpTextArea.setBorder(null);
        modelsDirHelpTextArea.setFocusable(false);
        modelsDirHelpTextArea.setText(
                "Choose the folder where local Hugging Face models are stored. "
                + "Download models saves all supported models here. Check models verifies that each required model folder contains basic model files."
        );

        statusTextArea.setEditable(false);
        statusTextArea.setLineWrap(true);
        statusTextArea.setWrapStyleWord(true);
        statusTextArea.setRows(8);
        statusScrollPane.setViewportView(statusTextArea);
        statusScrollPane.setPreferredSize(new Dimension(CONTENT_WIDTH, 150));
        configureHelpText(batchSizeHelpTextArea,
                "How many messages are processed together by the model. Larger values are faster, but use more memory.");
        configureHelpText(maxSeqLengthHelpTextArea,
                "Maximum number of model tokens kept from each message. Longer values preserve more text, but are slower.");
        configureHelpText(hateThresholdHelpTextArea,
                "Minimum hate score required for binary/multilabel models to mark a message as hate speech.");
        configureHelpText(useCudaHelpTextArea,
                "If enabled, the classifier tries to use an NVIDIA CUDA GPU when available and falls back to CPU otherwise.");
        configureHelpText(hateLabelsHelpTextArea,
                "Optional comma-separated labels used as hate/offensive classes. Leave blank to use automatic label detection.");
        hateThresholdSlider.setMajorTickSpacing(25);
        hateThresholdSlider.setMinorTickSpacing(5);
        hateThresholdSlider.setPaintTicks(true);
        hateThresholdSlider.addChangeListener(evt -> updateHateThresholdLabel());
        browseButton.addActionListener(evt -> chooseModelsDirectory());
        browseLogFileButton.addActionListener(evt -> chooseLogFilePath());
        browseEvaluationFileButton.addActionListener(evt -> chooseEvaluationFilePath());
        timeoutEnabledCheckBox.addActionListener(evt -> updateTimeoutEnabledState());
        downloadButton.addActionListener(evt -> runDownloadModels());
        checkButton.addActionListener(evt -> runCheckModels());

        JPanel contentPanel = new JPanel();
        GroupLayout layout = new GroupLayout(contentPanel);
        layout.setHorizontalGroup(
            layout.createParallelGroup(GroupLayout.Alignment.LEADING)
                .addGroup(layout.createSequentialGroup()
                    .addContainerGap()
                    .addGroup(layout.createParallelGroup(GroupLayout.Alignment.LEADING)
                        .addComponent(titleLabel)
                        .addComponent(modelsDirLabel)
                        .addComponent(modelsDirHelpTextArea, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                        .addGroup(layout.createSequentialGroup()
                            .addComponent(modelsDirField, GroupLayout.PREFERRED_SIZE, 390, GroupLayout.PREFERRED_SIZE)
                            .addGap(8)
                            .addComponent(browseButton))
                        .addGroup(layout.createSequentialGroup()
                            .addComponent(downloadButton)
                            .addGap(8)
                            .addComponent(checkButton))
                        .addComponent(downloadProgressBar, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                        .addComponent(statusScrollPane, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                        .addComponent(extendedSettingsLabel)
                        .addComponent(batchSizeHelpTextArea, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                        .addComponent(batchSizeLabel)
                        .addComponent(batchSizeComboBox, GroupLayout.PREFERRED_SIZE, 120, GroupLayout.PREFERRED_SIZE)
                        .addComponent(maxSeqLengthHelpTextArea, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                        .addComponent(maxSeqLengthLabel)
                        .addComponent(maxSeqLengthComboBox, GroupLayout.PREFERRED_SIZE, 120, GroupLayout.PREFERRED_SIZE)
                        .addComponent(hateThresholdHelpTextArea, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                        .addComponent(hateThresholdLabel)
                        .addGroup(layout.createSequentialGroup()
                            .addComponent(hateThresholdSlider, GroupLayout.PREFERRED_SIZE, 390, GroupLayout.PREFERRED_SIZE)
                            .addGap(8)
                            .addComponent(hateThresholdValueLabel, GroupLayout.PREFERRED_SIZE, 80, GroupLayout.PREFERRED_SIZE))
                        .addComponent(useCudaHelpTextArea, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                        .addComponent(useCudaCheckBox)
                        .addComponent(hateLabelsHelpTextArea, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                        .addComponent(hateLabelIdsLabel)
                        .addComponent(hateLabelIdsField, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                        .addComponent(hateLabelNamesLabel)
                        .addComponent(hateLabelNamesField, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                        .addComponent(timeoutLabel)
                        .addComponent(timeoutEnabledCheckBox)
                        .addGroup(layout.createSequentialGroup()
                            .addComponent(timeoutSecondsLabel)
                            .addGap(8)
                            .addComponent(timeoutSecondsField, GroupLayout.PREFERRED_SIZE, 120, GroupLayout.PREFERRED_SIZE))
                        .addComponent(logPathLabel)
                        .addComponent(logFileLabel)
                        .addGroup(layout.createSequentialGroup()
                            .addComponent(logFileField, GroupLayout.PREFERRED_SIZE, 390, GroupLayout.PREFERRED_SIZE)
                            .addGap(8)
                            .addComponent(browseLogFileButton))
                        .addComponent(evaluationFileLabel)
                        .addGroup(layout.createSequentialGroup()
                            .addComponent(evaluationFileField, GroupLayout.PREFERRED_SIZE, 390, GroupLayout.PREFERRED_SIZE)
                            .addGap(8)
                            .addComponent(browseEvaluationFileButton)))
                    .addContainerGap())
        );
        layout.setVerticalGroup(
            layout.createParallelGroup(GroupLayout.Alignment.LEADING)
                .addGroup(layout.createSequentialGroup()
                    .addContainerGap()
                    .addComponent(titleLabel)
                    .addGap(12)
                    .addComponent(modelsDirLabel)
                    .addGap(4)
                    .addComponent(modelsDirHelpTextArea, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                    .addGap(4)
                    .addGroup(layout.createParallelGroup(GroupLayout.Alignment.BASELINE)
                        .addComponent(modelsDirField, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                        .addComponent(browseButton))
                    .addGap(12)
                    .addGroup(layout.createParallelGroup(GroupLayout.Alignment.BASELINE)
                        .addComponent(downloadButton)
                        .addComponent(checkButton))
                    .addGap(8)
                    .addComponent(downloadProgressBar, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                    .addGap(8)
                    .addComponent(statusScrollPane, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                    .addGap(12)
                    .addComponent(extendedSettingsLabel)
                    .addGap(4)
                    .addComponent(batchSizeHelpTextArea, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                    .addGap(4)
                    .addComponent(batchSizeLabel)
                    .addGap(4)
                    .addComponent(batchSizeComboBox, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                    .addGap(8)
                    .addComponent(maxSeqLengthHelpTextArea, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                    .addGap(4)
                    .addComponent(maxSeqLengthLabel)
                    .addGap(4)
                    .addComponent(maxSeqLengthComboBox, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                    .addGap(8)
                    .addComponent(hateThresholdHelpTextArea, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                    .addGap(4)
                    .addComponent(hateThresholdLabel)
                    .addGap(4)
                    .addGroup(layout.createParallelGroup(GroupLayout.Alignment.CENTER)
                        .addComponent(hateThresholdSlider, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                        .addComponent(hateThresholdValueLabel))
                    .addGap(8)
                    .addComponent(useCudaHelpTextArea, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                    .addGap(4)
                    .addComponent(useCudaCheckBox)
                    .addGap(8)
                    .addComponent(hateLabelsHelpTextArea, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                    .addGap(4)
                    .addComponent(hateLabelIdsLabel)
                    .addGap(4)
                    .addComponent(hateLabelIdsField, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                    .addGap(4)
                    .addComponent(hateLabelNamesLabel)
                    .addGap(4)
                    .addComponent(hateLabelNamesField, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                    .addGap(12)
                    .addComponent(timeoutLabel)
                    .addGap(4)
                    .addComponent(timeoutEnabledCheckBox)
                    .addGap(4)
                    .addGroup(layout.createParallelGroup(GroupLayout.Alignment.BASELINE)
                        .addComponent(timeoutSecondsLabel)
                        .addComponent(timeoutSecondsField, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE))
                    .addGap(12)
                    .addComponent(logPathLabel)
                    .addGap(4)
                    .addComponent(logFileLabel)
                    .addGap(4)
                    .addGroup(layout.createParallelGroup(GroupLayout.Alignment.BASELINE)
                        .addComponent(logFileField, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                        .addComponent(browseLogFileButton))
                    .addGap(4)
                    .addComponent(evaluationFileLabel)
                    .addGap(4)
                    .addGroup(layout.createParallelGroup(GroupLayout.Alignment.BASELINE)
                        .addComponent(evaluationFileField, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                        .addComponent(browseEvaluationFileButton))
                    .addContainerGap())
        );
        contentPanel.setLayout(layout);

        JScrollPane contentScrollPane = new JScrollPane(contentPanel);
        contentScrollPane.setBorder(null);
        contentScrollPane.setPreferredSize(new Dimension(CONTENT_WIDTH + 40, 430));

        setLayout(new BorderLayout());
        add(contentScrollPane, BorderLayout.CENTER);
    }

    private void chooseModelsDirectory() {
        JFileChooser chooser = new JFileChooser(modelsDirField.getText());
        chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY);
        if (chooser.showOpenDialog(this) == JFileChooser.APPROVE_OPTION) {
            modelsDirField.setText(chooser.getSelectedFile().getAbsolutePath());
        }
    }

    private void chooseLogFilePath() {
        chooseFilePath(logFileField, "log");
    }

    private void chooseEvaluationFilePath() {
        chooseFilePath(evaluationFileField, "csv");
    }

    private void chooseFilePath(JTextField targetField, String extension) {
        JFileChooser chooser = new JFileChooser(targetField.getText());
        chooser.setFileSelectionMode(JFileChooser.FILES_ONLY);
        if (chooser.showSaveDialog(this) == JFileChooser.APPROVE_OPTION) {
            File selected = chooser.getSelectedFile();
            String path = selected.getAbsolutePath();
            if (!path.toLowerCase().endsWith("." + extension)) {
                path = path + "." + extension;
            }
            targetField.setText(path);
        }
    }

    private File selectedModelsDirectory() {
        String value = modelsDirField.getText();
        if (value == null || value.isBlank()) {
            return HateSpeechGlobalSettings.defaultModelsDirectory();
        }
        return new File(value.trim());
    }

    private void updateTimeoutEnabledState() {
        timeoutSecondsField.setEnabled(timeoutEnabledCheckBox.isSelected());
        timeoutSecondsLabel.setEnabled(timeoutEnabledCheckBox.isSelected());
    }

    private void updateHateThresholdLabel() {
        hateThresholdValueLabel.setText(String.format("%.2f", hateThresholdSlider.getValue() / 100.0));
    }

    private static void configureHelpText(JTextArea textArea, String text) {
        textArea.setEditable(false);
        textArea.setLineWrap(true);
        textArea.setWrapStyleWord(true);
        textArea.setRows(2);
        textArea.setOpaque(false);
        textArea.setBorder(null);
        textArea.setFocusable(false);
        textArea.setText(text);
    }

    private static int selectedInteger(JComboBox<Integer> comboBox, int fallback) {
        Object selected = comboBox.getSelectedItem();
        return selected instanceof Integer ? (Integer) selected : fallback;
    }

    private int parseTimeoutSeconds() {
        String raw = timeoutSecondsField.getText();
        if (raw == null || raw.trim().isEmpty()) {
            return DEFAULT_TIMEOUT_SECONDS;
        }
        try {
            int value = Integer.parseInt(raw.trim());
            return value > 0 ? value : DEFAULT_TIMEOUT_SECONDS;
        } catch (NumberFormatException ex) {
            return DEFAULT_TIMEOUT_SECONDS;
        }
    }

    private void runDownloadModels() {
        if (HateSpeechGlobalSettings.isModelDownloadInProgress()) {
            setStatus("Model download is already in progress.");
            return;
        }
        File exe = HateSpeechGlobalSettings.findCliExecutable();
        if (exe == null) {
            setStatus("Hate speech CLI executable was not found.");
            return;
        }
        File modelsDir = selectedModelsDirectory();
        HateSpeechGlobalSettings.setModelsDirectory(modelsDir.getAbsolutePath());
        setButtonsEnabled(false);
        setDownloadProgressVisible(true);
        HateSpeechGlobalSettings.setModelDownloadInProgress(true);
        File downloadLogFile = buildDownloadLogFile(modelsDir);
        setStatus("Downloading models to " + modelsDir.getAbsolutePath() + " ...\nLog file: " + downloadLogFile.getAbsolutePath());
        new SwingWorker<String, String>() {
            @Override
            protected String doInBackground() throws Exception {
                List<String> command = new ArrayList<>();
                command.add(exe.getAbsolutePath());
                command.add("--download-models");
                command.add("--download-dir");
                command.add(modelsDir.getAbsolutePath());
                command.add("--log-file");
                command.add(downloadLogFile.getAbsolutePath());
                return runCommand(command, line -> publish(line + "\n"));
            }

            @Override
            protected void process(List<String> chunks) {
                for (String chunk : chunks) {
                    appendStatus(chunk);
                }
            }

            @Override
            protected void done() {
                HateSpeechGlobalSettings.setModelDownloadInProgress(false);
                setButtonsEnabled(true);
                setDownloadProgressVisible(false);
                try {
                    get();
                    String message = "Hate Speech Detector models downloaded to " + modelsDir.getAbsolutePath() + ".";
                    appendStatus("\nDownload completed.\n");
                    postMessageToUser(IngestMessage.MessageType.INFO, message);
                } catch (Exception ex) {
                    String message = "Hate Speech Detector model download failed: " + unwrapMessage(ex);
                    appendStatus("\nDownload failed.\n\n" + unwrapMessage(ex));
                    postMessageToUser(IngestMessage.MessageType.ERROR, message);
                }
            }
        }.execute();
    }

    private void runCheckModels() {
        File modelsDir = selectedModelsDirectory();
        HateSpeechGlobalSettings.setModelsDirectory(modelsDir.getAbsolutePath());
        String[] aliases = {
            "electra_hatexplain",
            "roberta_dynabench_target",
            "roberta_twitter_hate_latest",
            "bert_hatexplain_cnerg"
        };
        StringBuilder sb = new StringBuilder();
        sb.append("Models folder: ").append(modelsDir.getAbsolutePath()).append('\n');
        if (!modelsDir.isDirectory()) {
            sb.append("Folder does not exist yet. Use Download models, or choose an existing models folder.\n");
        }
        for (String alias : aliases) {
            File modelDir = new File(modelsDir, alias);
            boolean exists = modelDir.isDirectory()
                    && new File(modelDir, "config.json").isFile()
                    && new File(modelDir, "tokenizer_config.json").isFile();
            sb.append(exists ? "[OK] " : "[MISSING] ").append(alias).append('\n');
        }
        setStatus(sb.toString());
    }

    private static String runCommand(List<String> command, Consumer<String> lineConsumer) throws IOException, InterruptedException {
        ProcessBuilder pb = new ProcessBuilder(command);
        pb.redirectErrorStream(true);
        Process process = pb.start();
        StringBuilder output = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line).append('\n');
                if (lineConsumer != null) {
                    lineConsumer.accept(line);
                }
            }
        }
        int exit = process.waitFor();
        if (exit != 0) {
            throw new IOException("Command exited with status " + exit + "\n" + output);
        }
        return output.toString();
    }

    private static String unwrapMessage(Exception ex) {
        Throwable current = ex;
        while (current.getCause() != null) {
            current = current.getCause();
        }
        String message = current.getMessage();
        return (message == null || message.isBlank()) ? current.toString() : message;
    }

    private static File buildDownloadLogFile(File modelsDir) {
        File baseDir = modelsDir.getParentFile();
        if (baseDir == null) {
            baseDir = modelsDir;
        }
        File logDir = new File(baseDir, "logs");
        String timestamp = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss").format(LocalDateTime.now());
        return new File(logDir, "hatespeech_download_" + timestamp + ".log");
    }

    private void setButtonsEnabled(boolean enabled) {
        browseButton.setEnabled(enabled);
        downloadButton.setEnabled(enabled);
        checkButton.setEnabled(enabled);
    }

    private void setDownloadProgressVisible(boolean visible) {
        downloadProgressBar.setVisible(visible);
    }

    private void setStatus(String text) {
        statusTextArea.setText(text == null ? "" : text);
        statusTextArea.setCaretPosition(0);
    }

    private void appendStatus(String text) {
        if (text == null || text.isEmpty()) {
            return;
        }
        statusTextArea.append(text);
        statusTextArea.setCaretPosition(statusTextArea.getDocument().getLength());
    }

    private static void postMessageToUser(IngestMessage.MessageType messageType, String message) {
        IngestServices.getInstance().postMessage(
            IngestMessage.createMessage(
                messageType,
                HateSpeechIngestModuleFactory.getModuleName(),
                message
            )
        );
    }
}
