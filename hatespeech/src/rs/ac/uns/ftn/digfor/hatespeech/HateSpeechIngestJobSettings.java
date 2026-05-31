package rs.ac.uns.ftn.digfor.hatespeech;

import org.sleuthkit.autopsy.ingest.IngestModuleIngestJobSettings;

public class HateSpeechIngestJobSettings implements IngestModuleIngestJobSettings {
    private static final long serialVersionUID = 1L;
    private static final int DEFAULT_TIMEOUT_SECONDS = 120;
    static final String MODEL_SOURCE_AUTO = "auto";
    static final String MODEL_SOURCE_OFFLINE = "offline";
    static final String MODEL_SOURCE_ONLINE = "online";
    private boolean skipKnownFiles = true;
    private String modelAlias = "electra_hatexplain";
    private String modelSource = MODEL_SOURCE_AUTO;
    private boolean includeEmail = true;
    private boolean includeSmsMms = true;
    private boolean includeWhatsApp = true;
    private boolean includeViber = true;
    private boolean includeTelegram = true;
    private boolean includeOtherMessages = true;
    private boolean timeoutEnabled = true;
    private int timeoutSeconds = DEFAULT_TIMEOUT_SECONDS;
    
    /**
     * Creates settings with default values.
     */
    public HateSpeechIngestJobSettings() {
    }
    
    /**
     * Creates settings with an explicit skip-known-files option.
     */
    public HateSpeechIngestJobSettings(boolean skipKnownFiles) {
        this.skipKnownFiles = skipKnownFiles;
    }
    
    /**
     * Creates settings with an explicit skip-known-files option and model alias.
     */
    public HateSpeechIngestJobSettings(boolean skipKnownFiles, String modelAlias) {
        this.skipKnownFiles = skipKnownFiles;
        this.modelAlias = modelAlias;
    }
    
    /**
     * Creates fully specified ingest job settings.
     */
    public HateSpeechIngestJobSettings(
            boolean skipKnownFiles,
            String modelAlias,
            boolean includeEmail,
            boolean includeSmsMms,
            boolean includeWhatsApp,
            boolean includeViber,
            boolean includeTelegram,
            boolean includeOtherMessages,
            boolean timeoutEnabled,
            int timeoutSeconds
    ) {
        this(
                skipKnownFiles,
                modelAlias,
                includeEmail,
                includeSmsMms,
                includeWhatsApp,
                includeViber,
                includeTelegram,
                includeOtherMessages,
                timeoutEnabled,
                timeoutSeconds,
                MODEL_SOURCE_AUTO
        );
    }

    /**
     * Creates fully specified ingest job settings.
     */
    public HateSpeechIngestJobSettings(
            boolean skipKnownFiles,
            String modelAlias,
            boolean includeEmail,
            boolean includeSmsMms,
            boolean includeWhatsApp,
            boolean includeViber,
            boolean includeTelegram,
            boolean includeOtherMessages,
            boolean timeoutEnabled,
            int timeoutSeconds,
            String modelSource
    ) {
        this.skipKnownFiles = skipKnownFiles;
        this.modelAlias = modelAlias;
        this.includeEmail = includeEmail;
        this.includeSmsMms = includeSmsMms;
        this.includeWhatsApp = includeWhatsApp;
        this.includeViber = includeViber;
        this.includeTelegram = includeTelegram;
        this.includeOtherMessages = includeOtherMessages;
        this.timeoutEnabled = timeoutEnabled;
        this.timeoutSeconds = normalizeTimeoutSeconds(timeoutSeconds);
        this.modelSource = normalizeModelSource(modelSource);
    }

    /**
     * Returns the settings version for serialization compatibility.
     */
    @Override
    public long getVersionNumber() {
        return serialVersionUID;
    }
    
    /**
     * Enables or disables skipping known files.
     */
    void setSkipKnownFiles(boolean enabled) {
        skipKnownFiles = enabled;
    }

    /**
     * Returns whether known files should be skipped.
     */
    boolean skipKnownFiles() {
        return skipKnownFiles;
    }
    
    /**
     * Sets the model alias, falling back to default if blank.
     */
    void setModelAlias(String modelAlias) {
        if (modelAlias == null || modelAlias.isBlank()) {
            this.modelAlias = "electra_hatexplain";
        } else {
            this.modelAlias = modelAlias;
        }
    }
    
    /**
     * Returns the configured model alias.
     */
    String getModelAlias() {
        return modelAlias;
    }

    /**
     * Sets model source: auto, offline, or online.
     */
    void setModelSource(String modelSource) {
        this.modelSource = normalizeModelSource(modelSource);
    }

    /**
     * Returns model source: auto, offline, or online.
     */
    String getModelSource() {
        return normalizeModelSource(modelSource);
    }
    
    /**
     * Returns whether email artifacts are included.
     */
    boolean includeEmail() {
        return includeEmail;
    }
    
    /**
     * Returns whether SMS/MMS artifacts are included.
     */
    boolean includeSmsMms() {
        return includeSmsMms;
    }
    
    /**
     * Returns whether WhatsApp artifacts are included.
     */
    boolean includeWhatsApp() {
        return includeWhatsApp;
    }
    
    /**
     * Returns whether Viber artifacts are included.
     */
    boolean includeViber() {
        return includeViber;
    }
    
    /**
     * Returns whether Telegram artifacts are included.
     */
    boolean includeTelegram() {
        return includeTelegram;
    }
    
    /**
     * Returns whether other/unknown message artifacts are included.
     */
    boolean includeOtherMessages() {
        return includeOtherMessages;
    }

    /**
     * Returns whether timeout enforcement is enabled.
     */
    boolean isTimeoutEnabled() {
        return timeoutEnabled;
    }

    /**
     * Enables or disables the timeout.
     */
    void setTimeoutEnabled(boolean enabled) {
        timeoutEnabled = enabled;
    }

    /**
     * Returns the timeout value in seconds.
     */
    int getTimeoutSeconds() {
        return timeoutSeconds;
    }

    /**
     * Sets the timeout value in seconds, applying defaults for invalid input.
     */
    void setTimeoutSeconds(int seconds) {
        this.timeoutSeconds = normalizeTimeoutSeconds(seconds);
    }

    /**
     * Normalizes timeout seconds to a positive value.
     */
    private static int normalizeTimeoutSeconds(int seconds) {
        return seconds <= 0 ? DEFAULT_TIMEOUT_SECONDS : seconds;
    }

    private static String normalizeModelSource(String value) {
        if (value == null) {
            return MODEL_SOURCE_AUTO;
        }
        String normalized = value.trim().toLowerCase();
        switch (normalized) {
            case MODEL_SOURCE_OFFLINE:
            case MODEL_SOURCE_ONLINE:
            case MODEL_SOURCE_AUTO:
                return normalized;
            default:
                return MODEL_SOURCE_AUTO;
        }
    }
    
}
