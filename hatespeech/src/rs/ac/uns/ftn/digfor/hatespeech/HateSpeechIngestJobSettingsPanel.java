package rs.ac.uns.ftn.digfor.hatespeech;

import org.sleuthkit.autopsy.ingest.IngestModuleIngestJobSettings;
import org.sleuthkit.autopsy.ingest.IngestModuleIngestJobSettingsPanel;
import java.awt.Desktop;
import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.awt.Dimension;
import javax.swing.GroupLayout;
import javax.swing.JComboBox;
import javax.swing.JCheckBox;
import javax.swing.JEditorPane;
import javax.swing.JLabel;
import javax.swing.JScrollPane;
import javax.swing.JSeparator;
import javax.swing.JTextArea;
import javax.swing.DefaultComboBoxModel;
import org.openide.util.NbBundle;
import org.openide.awt.Mnemonics;
import org.openide.util.Exceptions;

@SuppressWarnings("PMD.SingularField") // UI widgets cause lots of false positives
public class HateSpeechIngestJobSettingsPanel extends IngestModuleIngestJobSettingsPanel {
    private static final String DEFAULT_MODEL_ALIAS = "electra_hatexplain";
    private static final String ALL_MODELS_ALIAS = "all";
    private static final int CONTENT_WIDTH = 340;
    private static final String ARTIFACT_CATALOG_DOC_URL = "https://sleuthkit.org/sleuthkit/docs/jni-docs/4.13.0/artifact_catalog_page.html";
    private final List<ModelEntry> modelEntries = new ArrayList<>();
    private boolean updatingSources = false;

    /**
     * Private constructor; use {@link #create(HateSpeechIngestJobSettings)}.
     */
    private HateSpeechIngestJobSettingsPanel() {
    }

    /**
     * Creates and initializes the settings panel.
     */
    static HateSpeechIngestJobSettingsPanel create(HateSpeechIngestJobSettings hateSpeechIngestJobSettings) {
        HateSpeechIngestJobSettingsPanel panel = new HateSpeechIngestJobSettingsPanel();
        panel.initComponents();
        panel.customizeComponents(hateSpeechIngestJobSettings);
        return panel;
    }
    
    // Initialize UI state based on persisted settings and runtime metadata.
    private void customizeComponents(HateSpeechIngestJobSettings settings) {
        List<ModelEntry> loaded = loadModelCatalog();
        modelEntries.clear();
        modelEntries.add(new ModelEntry(
                ALL_MODELS_ALIAS,
                "All configured local model folders",
                "All configured online model IDs",
                "Runs every supported model and combines the results for the same source message."
        ));
        modelEntries.addAll(loaded);
        DefaultComboBoxModel<ModelEntry> model = new DefaultComboBoxModel<>();
        for (ModelEntry entry : modelEntries) {
            model.addElement(entry);
        }
        modelComboBox.setModel(model);
        ModelEntry preferred = findByAlias(settings.getModelAlias());
        if (preferred != null) {
            modelComboBox.setSelectedItem(preferred);
        } else if (model.getSize() > 0) {
            modelComboBox.setSelectedIndex(0);
        }
        modelSourceComboBox.setSelectedItem(settings.getModelSource());
        updateModelDescription();
        sourcesEmailCheckBox.setSelected(settings.includeEmail());
        sourcesSmsCheckBox.setSelected(settings.includeSmsMms());
        sourcesWhatsAppCheckBox.setSelected(settings.includeWhatsApp());
        sourcesViberCheckBox.setSelected(settings.includeViber());
        sourcesTelegramCheckBox.setSelected(settings.includeTelegram());
        sourcesOtherCheckBox.setSelected(settings.includeOtherMessages());
        updateSourcesAllCheckBox();
        prereqValueTextArea.setText(NbBundle.getMessage(
                HateSpeechIngestJobSettingsPanel.class,
                "HateSpeechIngestJobSettingsPanel.prereqValueLabel.text"
        ));
        prereqValueTextArea.setCaretPosition(0);
    }

    /**
     * Collects the current UI state into ingest job settings.
     */
    @Override
    public IngestModuleIngestJobSettings getSettings() {
        return new HateSpeechIngestJobSettings(
                false,
                getSelectedModelAlias(),
                sourcesEmailCheckBox.isSelected(),
                sourcesSmsCheckBox.isSelected(),
                sourcesWhatsAppCheckBox.isSelected(),
                sourcesViberCheckBox.isSelected(),
                sourcesTelegramCheckBox.isSelected(),
                sourcesOtherCheckBox.isSelected(),
                HateSpeechGlobalSettings.isTimeoutEnabled(),
                HateSpeechGlobalSettings.getTimeoutSeconds(),
                getSelectedModelSource()
        );
    }

    // Returns selected model alias or default if nothing is selected.
    private String getSelectedModelAlias() {
        Object selected = modelComboBox.getSelectedItem();
        if (selected instanceof ModelEntry) {
            return ((ModelEntry) selected).alias;
        }
        return DEFAULT_MODEL_ALIAS;
    }

    private String getSelectedModelSource() {
        Object selected = modelSourceComboBox.getSelectedItem();
        return selected == null ? HateSpeechIngestJobSettings.MODEL_SOURCE_AUTO : selected.toString();
    }
    
    // Finds a model entry by alias (case-insensitive).
    private ModelEntry findByAlias(String alias) {
        if (alias == null) {
            return null;
        }
        for (ModelEntry entry : modelEntries) {
            if (alias.equalsIgnoreCase(entry.alias)) {
                return entry;
            }
        }
        return null;
    }
    
    // Updates the model description text area based on current selection.
    private void updateModelDescription() {
        Object selected = modelComboBox.getSelectedItem();
        if (!(selected instanceof ModelEntry)) {
            modelDescriptionTextArea.setText("No description available for the selected model.");
            modelDescriptionTextArea.setCaretPosition(0);
            return;
        }
        ModelEntry entry = (ModelEntry) selected;
        StringBuilder sb = new StringBuilder();
        String alias = (entry.alias == null || entry.alias.isBlank())
                ? "Not available."
                : entry.alias.trim();
        sb.append("Model Alias: ").append(alias);
        String modelId = (entry.offlineModelId == null || entry.offlineModelId.isBlank())
                ? "Not available."
                : entry.offlineModelId.trim();
        sb.append("\nOffline Model ID: ").append(modelId);
        String onlineModelId = (entry.onlineModelId == null || entry.onlineModelId.isBlank())
                ? "Not available."
                : entry.onlineModelId.trim();
        sb.append("\nOnline Model ID: ").append(onlineModelId);
        
        String description = (entry.description == null || entry.description.isBlank())
                ? "Not available."
                : entry.description.trim();
        sb.append("\nModel Description: ").append(description);
        modelDescriptionTextArea.setText(sb.toString());
        modelDescriptionTextArea.setCaretPosition(0);
    }

    // Toggles all source checkboxes when "All sources" is clicked.
    private void handleSourcesAllToggle() {
        if (updatingSources) {
            return;
        }
        updatingSources = true;
        boolean selected = sourcesAllCheckBox.isSelected();
        sourcesEmailCheckBox.setSelected(selected);
        sourcesSmsCheckBox.setSelected(selected);
        sourcesWhatsAppCheckBox.setSelected(selected);
        sourcesViberCheckBox.setSelected(selected);
        sourcesTelegramCheckBox.setSelected(selected);
        sourcesOtherCheckBox.setSelected(selected);
        updatingSources = false;
    }
    
    // Keeps the "All sources" checkbox in sync with individual selections.
    private void updateSourcesAllCheckBox() {
        if (updatingSources) {
            return;
        }
        updatingSources = true;
        boolean allSelected = sourcesEmailCheckBox.isSelected()
                && sourcesSmsCheckBox.isSelected()
                && sourcesWhatsAppCheckBox.isSelected()
                && sourcesViberCheckBox.isSelected()
                && sourcesTelegramCheckBox.isSelected()
                && sourcesOtherCheckBox.isSelected();
        sourcesAllCheckBox.setSelected(allSelected);
        updatingSources = false;
    }

    private void openDocumentationLink(String url) {
        if (!Desktop.isDesktopSupported()) {
            return;
        }
        try {
            Desktop.getDesktop().browse(URI.create(url));
        } catch (IOException | IllegalArgumentException ex) {
            Exceptions.printStackTrace(ex);
        }
    }

    // Loads model catalog from the packaged CLI and falls back to a static list if needed.
    private List<ModelEntry> loadModelCatalog() {
        List<ModelEntry> fromCli = loadModelCatalogFromCli();
        if (!fromCli.isEmpty()) {
            return fromCli;
        }
        return getFallbackModelCatalog();
    }
    
    // Executes the packaged CLI with `--list-models` and parses its table output.
    private List<ModelEntry> loadModelCatalogFromCli() {
        File exe = findCliExecutable();
        if (exe == null) {
            return Collections.emptyList();
        }
        List<String> lines = new ArrayList<>();
        File listModelsLogFile = buildListModelsLogFile();
        ProcessBuilder pb = new ProcessBuilder(
                exe.getAbsolutePath(),
                "--list-models",
                "--log-file",
                listModelsLogFile.getAbsolutePath()
        );
        try {
            Process p = pb.start();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    lines.add(line);
                }
            }
            int exit = p.waitFor();
            if (exit != 0) {
                return Collections.emptyList();
            }
        } catch (IOException | InterruptedException ex) {
            Exceptions.printStackTrace(ex);
            return Collections.emptyList();
        }
        return parseModelCatalog(lines);
    }

    private File buildListModelsLogFile() {
        File modelsDir = new File(HateSpeechGlobalSettings.getModelsDirectory());
        File baseDir = modelsDir.getParentFile();
        if (baseDir == null) {
            baseDir = modelsDir;
        }
        return new File(new File(baseDir, "logs"), "hatespeech_list_models.log");
    }
    
    // Parses the CLI table into model entries.
    private List<ModelEntry> parseModelCatalog(List<String> lines) {
        List<ModelEntry> entries = new ArrayList<>();
        for (String line : lines) {
            if (line == null) {
                continue;
            }
            String trimmed = line.trim();
            if (trimmed.isEmpty()) {
                continue;
            }
            if (trimmed.startsWith("alias") || trimmed.startsWith("---") || trimmed.contains("-+-")) {
                continue;
            }
            String[] parts = trimmed.split("\\s\\|\\s");
            if (parts.length < 3) {
                continue;
            }
            String alias = parts[0].trim();
            String offlineModelId = parts[2].trim();
            String onlineModelId = parts.length >= 4 ? parts[3].trim() : "";
            if (alias.isBlank() || alias.contains(":") || offlineModelId.isBlank()) {
                continue;
            }
            String description = "";
            if (parts.length >= 5) {
                StringBuilder descBuilder = new StringBuilder();
                for (int i = 4; i < parts.length; i++) {
                    if (descBuilder.length() > 0) {
                        descBuilder.append(" | ");
                    }
                    descBuilder.append(parts[i].trim());
                }
                description = descBuilder.toString();
            }
            entries.add(new ModelEntry(alias, offlineModelId, onlineModelId, description));
        }
        return entries;
    }
    
    // Fallback model list used when Python CLI is unavailable.
    private List<ModelEntry> getFallbackModelCatalog() {
        List<ModelEntry> entries = new ArrayList<>();
        entries.add(new ModelEntry(
                "electra_hatexplain",
                "models/electra_hatexplain",
                "TehranNLP-org/electra-base-hateXplain",
                "Good choice for broader screening. Tends to flag more potentially hateful or offensive content and is useful when higher recall is preferred over stricter precision.\nModel: google/electra-base-discriminator fine-tuned on the HateXplain dataset."
        ));
        entries.add(new ModelEntry(
                "roberta_dynabench_target",
                "models/roberta_dynabench_target",
                "facebook/roberta-hate-speech-dynabench-r4-target",
                "Strong general-purpose option for hate speech detection, especially when you want a balanced tradeoff between accuracy, precision, and recall.\nModel: Facebook RoBERTa model released for dynamically generated online hate detection data in the R4 target setting."
        ));
        entries.add(new ModelEntry(
                "roberta_twitter_hate_latest",
                "models/roberta_twitter_hate_latest",
                "cardiffnlp/twitter-roberta-base-hate-latest",
                "Well suited for short social-media style posts. Often more precise on concise, platform-like messages such as tweets or brief comments.\nModel: cardiffnlp/twitter-roberta-base-2022-154m fine-tuned as a binary hate-speech classifier on a combination of 13 English hate-speech datasets."
        ));
        entries.add(new ModelEntry(
                "bert_hatexplain_cnerg",
                "models/bert_hatexplain_cnerg",
                "Hate-speech-CNERG/bert-base-uncased-hatexplain",
                "More conservative HateXplain-based option. Useful when you want stronger precision and fewer false positives, especially on explicit abusive language.\nModel: bert-base-uncased classifier trained on the HateXplain dataset from Gab and Twitter, with human rationales incorporated during training."
        ));
        return entries;
    }
    
    // Locates the packaged CLI executable for `--list-models`.
    private File findCliExecutable() {
        return HateSpeechGlobalSettings.findCliExecutable();
    }

    // Simple value object for model metadata.
    private static class ModelEntry {
        private final String alias;
        private final String offlineModelId;
        private final String onlineModelId;
        private final String description;

        private ModelEntry(String alias, String offlineModelId, String onlineModelId, String description) {
            this.alias = alias;
            this.offlineModelId = offlineModelId;
            this.onlineModelId = onlineModelId;
            this.description = description;
        }

        /**
         * Displays the model alias in the combo box.
         */
        @Override
        public String toString() {
            return alias;
        }
    }
    
    // Variables declaration - do not modify//GEN-BEGIN:variables
    private JLabel titleLabel;
    private JComboBox<ModelEntry> modelComboBox;
    private JLabel modelSourceLabel;
    private JComboBox<String> modelSourceComboBox;
    private JTextArea modelSourceHelpTextArea;
    private JLabel modelLabel;
    private JLabel modelDescriptionLabel;
    private JTextArea modelDescriptionTextArea;
    private JScrollPane modelDescriptionScrollPane;
    private JLabel sourcesLabel;
    private JCheckBox sourcesAllCheckBox;
    private JCheckBox sourcesEmailCheckBox;
    private JCheckBox sourcesSmsCheckBox;
    private JCheckBox sourcesWhatsAppCheckBox;
    private JCheckBox sourcesViberCheckBox;
    private JCheckBox sourcesTelegramCheckBox;
    private JCheckBox sourcesOtherCheckBox;
    private JEditorPane sourcesHelpEditorPane;
    private JLabel prereqLabel;
    private JTextArea prereqValueTextArea;
    private JSeparator prereqSeparator;
    private JSeparator sourcesSeparator;
    private JSeparator modelSeparator;
    // End of variables declaration//GEN-END:variables
    
    @SuppressWarnings("unchecked")
    // <editor-fold defaultstate="collapsed" desc="Generated Code">//GEN-BEGIN:initComponents
    private void initComponents() {
        titleLabel = new JLabel();
        modelLabel = new JLabel();
        modelComboBox = new JComboBox<>();
        modelSourceLabel = new JLabel();
        modelSourceComboBox = new JComboBox<>();
        modelSourceHelpTextArea = new JTextArea();
        modelDescriptionLabel = new JLabel();
        modelDescriptionTextArea = new JTextArea();
        modelDescriptionScrollPane = new JScrollPane();
        sourcesLabel = new JLabel();
        sourcesAllCheckBox = new JCheckBox();
        sourcesEmailCheckBox = new JCheckBox();
        sourcesSmsCheckBox = new JCheckBox();
        sourcesWhatsAppCheckBox = new JCheckBox();
        sourcesViberCheckBox = new JCheckBox();
        sourcesTelegramCheckBox = new JCheckBox();
        sourcesOtherCheckBox = new JCheckBox();
        sourcesHelpEditorPane = new JEditorPane();
        prereqLabel = new JLabel();
        prereqValueTextArea = new JTextArea();
        prereqSeparator = new JSeparator();
        sourcesSeparator = new JSeparator();
        modelSeparator = new JSeparator();
        
        Mnemonics.setLocalizedText(
                titleLabel,
                NbBundle.getMessage(
                        HateSpeechIngestJobSettingsPanel.class,
                        "HateSpeechIngestJobSettingsPanel.titleLabel.text"
                )
        ); // NOI18N

        Mnemonics.setLocalizedText(
                modelLabel,
                NbBundle.getMessage(
                        HateSpeechIngestJobSettingsPanel.class,
                        "HateSpeechIngestJobSettingsPanel.modelLabel.text"
                )
        ); // NOI18N

        Mnemonics.setLocalizedText(
                sourcesLabel,
                NbBundle.getMessage(
                        HateSpeechIngestJobSettingsPanel.class,
                        "HateSpeechIngestJobSettingsPanel.sourcesLabel.text"
                )
        ); // NOI18N

        Mnemonics.setLocalizedText(
                sourcesAllCheckBox,
                NbBundle.getMessage(
                        HateSpeechIngestJobSettingsPanel.class,
                        "HateSpeechIngestJobSettingsPanel.sourcesAllCheckBox.text"
                )
        ); // NOI18N

        Mnemonics.setLocalizedText(
                sourcesEmailCheckBox,
                NbBundle.getMessage(
                        HateSpeechIngestJobSettingsPanel.class,
                        "HateSpeechIngestJobSettingsPanel.sourcesEmailCheckBox.text"
                )
        ); // NOI18N

        Mnemonics.setLocalizedText(
                sourcesSmsCheckBox,
                NbBundle.getMessage(
                        HateSpeechIngestJobSettingsPanel.class,
                        "HateSpeechIngestJobSettingsPanel.sourcesSmsCheckBox.text"
                )
        ); // NOI18N

        Mnemonics.setLocalizedText(
                sourcesWhatsAppCheckBox,
                NbBundle.getMessage(
                        HateSpeechIngestJobSettingsPanel.class,
                        "HateSpeechIngestJobSettingsPanel.sourcesWhatsAppCheckBox.text"
                )
        ); // NOI18N

        Mnemonics.setLocalizedText(
                sourcesViberCheckBox,
                NbBundle.getMessage(
                        HateSpeechIngestJobSettingsPanel.class,
                        "HateSpeechIngestJobSettingsPanel.sourcesViberCheckBox.text"
                )
        ); // NOI18N

        Mnemonics.setLocalizedText(
                sourcesTelegramCheckBox,
                NbBundle.getMessage(
                        HateSpeechIngestJobSettingsPanel.class,
                        "HateSpeechIngestJobSettingsPanel.sourcesTelegramCheckBox.text"
                )
        ); // NOI18N

        Mnemonics.setLocalizedText(
                sourcesOtherCheckBox,
                NbBundle.getMessage(
                        HateSpeechIngestJobSettingsPanel.class,
                        "HateSpeechIngestJobSettingsPanel.sourcesOtherCheckBox.text"
                )
        ); // NOI18N
        
        Mnemonics.setLocalizedText(
                modelDescriptionLabel,
                NbBundle.getMessage(
                        HateSpeechIngestJobSettingsPanel.class,
                        "HateSpeechIngestJobSettingsPanel.modelDescriptionLabel.text"
                )
        ); // NOI18N

        Mnemonics.setLocalizedText(
                modelSourceLabel,
                NbBundle.getMessage(
                        HateSpeechIngestJobSettingsPanel.class,
                        "HateSpeechIngestJobSettingsPanel.modelSourceLabel.text"
                )
        ); // NOI18N
        
        Mnemonics.setLocalizedText(
                prereqLabel,
                NbBundle.getMessage(
                        HateSpeechIngestJobSettingsPanel.class,
                        "HateSpeechIngestJobSettingsPanel.prereqLabel.text"
                )
        ); // NOI18N

        modelDescriptionTextArea.setEditable(false);
        modelDescriptionTextArea.setLineWrap(true);
        modelDescriptionTextArea.setWrapStyleWord(true);
        modelDescriptionTextArea.setRows(7);
        modelDescriptionTextArea.setOpaque(true);
        modelDescriptionScrollPane.setViewportView(modelDescriptionTextArea);
        modelDescriptionScrollPane.setBorder(null);
        modelDescriptionScrollPane.setPreferredSize(new Dimension(CONTENT_WIDTH, 150));
        modelDescriptionScrollPane.setMinimumSize(new Dimension(CONTENT_WIDTH, 150));
        modelSourceComboBox.setModel(new DefaultComboBoxModel<>(new String[] {
            HateSpeechIngestJobSettings.MODEL_SOURCE_AUTO,
            HateSpeechIngestJobSettings.MODEL_SOURCE_OFFLINE,
            HateSpeechIngestJobSettings.MODEL_SOURCE_ONLINE
        }));
        modelSourceHelpTextArea.setEditable(false);
        modelSourceHelpTextArea.setLineWrap(true);
        modelSourceHelpTextArea.setWrapStyleWord(true);
        modelSourceHelpTextArea.setRows(3);
        modelSourceHelpTextArea.setOpaque(false);
        modelSourceHelpTextArea.setBorder(null);
        modelSourceHelpTextArea.setFocusable(false);
        modelSourceHelpTextArea.setText(
                "auto: use the local model if it exists; otherwise use the online Hugging Face model.\n"
                + "offline: use only local models and fail if missing.\n"
                + "online: always use the online model ID."
        );
        sourcesHelpEditorPane.setEditable(false);
        sourcesHelpEditorPane.setContentType("text/html");
        sourcesHelpEditorPane.setOpaque(false);
        sourcesHelpEditorPane.setBorder(null);
        sourcesHelpEditorPane.setFocusable(false);
        sourcesHelpEditorPane.setText(
                "<html><body style='font-family:sans-serif;font-size:10pt;margin:0;width:320px;'>"
                + "Artifacts are produced by Email Parser, Android Analyzer, and iOS Analyzer.<br>"
                + "Documentation: <a href='" + ARTIFACT_CATALOG_DOC_URL + "'>"
                + ARTIFACT_CATALOG_DOC_URL
                + "</a>"
                + "</body></html>"
        );
        sourcesHelpEditorPane.addHyperlinkListener(evt -> {
            if (evt.getEventType() == javax.swing.event.HyperlinkEvent.EventType.ACTIVATED) {
                openDocumentationLink(evt.getURL() == null ? ARTIFACT_CATALOG_DOC_URL : evt.getURL().toString());
            }
        });

        prereqValueTextArea.setEditable(false);
        prereqValueTextArea.setLineWrap(true);
        prereqValueTextArea.setWrapStyleWord(true);
        prereqValueTextArea.setRows(2);
        prereqValueTextArea.setOpaque(false);
        prereqValueTextArea.setBorder(null);
        prereqValueTextArea.setFocusable(false);

        modelComboBox.addActionListener(evt -> updateModelDescription());
        sourcesAllCheckBox.addActionListener(evt -> handleSourcesAllToggle());
        sourcesEmailCheckBox.addActionListener(evt -> updateSourcesAllCheckBox());
        sourcesSmsCheckBox.addActionListener(evt -> updateSourcesAllCheckBox());
        sourcesWhatsAppCheckBox.addActionListener(evt -> updateSourcesAllCheckBox());
        sourcesViberCheckBox.addActionListener(evt -> updateSourcesAllCheckBox());
        sourcesTelegramCheckBox.addActionListener(evt -> updateSourcesAllCheckBox());
        sourcesOtherCheckBox.addActionListener(evt -> updateSourcesAllCheckBox());

        GroupLayout layout = new GroupLayout(this);
        
        layout.setHorizontalGroup(
            layout.createParallelGroup(GroupLayout.Alignment.LEADING)
            .addGroup(layout.createSequentialGroup()
                .addContainerGap()
                .addGroup(layout.createParallelGroup(GroupLayout.Alignment.LEADING)
                    .addComponent(titleLabel)
                    .addComponent(prereqLabel)
                    .addComponent(prereqValueTextArea, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                    .addComponent(prereqSeparator, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                    .addComponent(sourcesLabel)
                    .addComponent(sourcesAllCheckBox)
                    .addComponent(sourcesEmailCheckBox)
                    .addComponent(sourcesSmsCheckBox)
                    .addComponent(sourcesWhatsAppCheckBox)
                    .addComponent(sourcesViberCheckBox)
                    .addComponent(sourcesTelegramCheckBox)
                    .addComponent(sourcesOtherCheckBox)
                    .addComponent(sourcesHelpEditorPane, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                    .addComponent(sourcesSeparator, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                    .addComponent(modelLabel)
                    .addComponent(modelComboBox, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                    .addComponent(modelSourceLabel)
                    .addComponent(modelSourceComboBox, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                    .addComponent(modelSourceHelpTextArea, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                    .addComponent(modelDescriptionLabel)
                    .addComponent(modelDescriptionScrollPane, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE)
                    .addComponent(modelSeparator, GroupLayout.PREFERRED_SIZE, CONTENT_WIDTH, GroupLayout.PREFERRED_SIZE))
                .addContainerGap())
        );
        layout.setVerticalGroup(
            layout.createParallelGroup(GroupLayout.Alignment.LEADING)
            .addGroup(layout.createSequentialGroup()
                .addContainerGap()
                .addComponent(titleLabel)
                .addGap(8)
                .addComponent(prereqLabel)
                .addGap(4)
                .addComponent(prereqValueTextArea, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                .addGap(6)
                .addComponent(prereqSeparator, GroupLayout.PREFERRED_SIZE, 6, GroupLayout.PREFERRED_SIZE)
                .addGap(8)
                .addComponent(sourcesLabel)
                .addGap(4)
                .addComponent(sourcesAllCheckBox)
                .addGap(4)
                .addComponent(sourcesEmailCheckBox)
                .addGap(4)
                .addComponent(sourcesSmsCheckBox)
                .addGap(4)
                .addComponent(sourcesWhatsAppCheckBox)
                .addGap(4)
                .addComponent(sourcesViberCheckBox)
                .addGap(4)
                .addComponent(sourcesTelegramCheckBox)
                .addGap(4)
                .addComponent(sourcesOtherCheckBox)
                .addGap(4)
                .addComponent(sourcesHelpEditorPane, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                .addGap(6)
                .addComponent(sourcesSeparator, GroupLayout.PREFERRED_SIZE, 6, GroupLayout.PREFERRED_SIZE)
                .addGap(8)
                .addComponent(modelLabel)
                .addGap(4)
                .addComponent(modelComboBox, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                .addGap(8)
                .addComponent(modelSourceLabel)
                .addGap(4)
                .addComponent(modelSourceComboBox, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                .addGap(4)
                .addComponent(modelSourceHelpTextArea, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                .addGap(8)
                .addComponent(modelDescriptionLabel)
                .addGap(4)
                .addComponent(modelDescriptionScrollPane, GroupLayout.PREFERRED_SIZE, GroupLayout.DEFAULT_SIZE, GroupLayout.PREFERRED_SIZE)
                .addGap(6)
                .addComponent(modelSeparator, GroupLayout.PREFERRED_SIZE, 6, GroupLayout.PREFERRED_SIZE)
                .addContainerGap(12, Short.MAX_VALUE))
        );
        this.setLayout(layout);
    }// </editor-fold>//GEN-END:initComponents
    
    
    
}
