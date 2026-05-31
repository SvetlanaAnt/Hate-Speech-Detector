package rs.ac.uns.ftn.digfor.hatespeech;

import java.io.File;
import java.util.prefs.Preferences;
import org.sleuthkit.autopsy.casemodule.Case;
import org.sleuthkit.autopsy.casemodule.NoCurrentCaseException;
import org.openide.modules.InstalledFileLocator;
import org.openide.util.NbPreferences;

final class HateSpeechGlobalSettings {
    private static final String MODELS_DIR_KEY = "modelsDirectory";
    private static final String LOG_FILE_PATTERN_KEY = "logFilePattern";
    private static final String EVALUATION_FILE_PATTERN_KEY = "evaluationFilePattern";
    private static final String TIMEOUT_ENABLED_KEY = "timeoutEnabled";
    private static final String TIMEOUT_SECONDS_KEY = "timeoutSeconds";
    private static final String BATCH_SIZE_KEY = "batchSize";
    private static final String MAX_SEQ_LENGTH_KEY = "maxSeqLength";
    private static final String HATE_THRESHOLD_KEY = "hateThreshold";
    private static final String USE_CUDA_KEY = "useCuda";
    private static final String HATE_LABEL_IDS_KEY = "hateLabelIds";
    private static final String HATE_LABEL_NAMES_KEY = "hateLabelNames";
    private static final int DEFAULT_TIMEOUT_SECONDS = 900;
    private static final int DEFAULT_BATCH_SIZE = 32;
    private static final int DEFAULT_MAX_SEQ_LENGTH = 512;
    private static final double DEFAULT_HATE_THRESHOLD = 0.5;
    private static volatile boolean modelDownloadInProgress = false;

    private HateSpeechGlobalSettings() {
    }

    static String getModelsDirectory() {
        return preferences().get(MODELS_DIR_KEY, defaultModelsDirectory().getAbsolutePath());
    }

    static void setModelsDirectory(String path) {
        if (path == null || path.isBlank()) {
            preferences().remove(MODELS_DIR_KEY);
        } else {
            preferences().put(MODELS_DIR_KEY, path.trim());
        }
    }

    static String getLogFilePattern() {
        return preferences().get(LOG_FILE_PATTERN_KEY, defaultLogFilePattern());
    }

    static void setLogFilePattern(String path) {
        if (path == null || path.isBlank()) {
            preferences().remove(LOG_FILE_PATTERN_KEY);
        } else {
            preferences().put(LOG_FILE_PATTERN_KEY, path.trim());
        }
    }

    static String getEvaluationFilePattern() {
        return preferences().get(EVALUATION_FILE_PATTERN_KEY, defaultEvaluationFilePattern());
    }

    static void setEvaluationFilePattern(String path) {
        if (path == null || path.isBlank()) {
            preferences().remove(EVALUATION_FILE_PATTERN_KEY);
        } else {
            preferences().put(EVALUATION_FILE_PATTERN_KEY, path.trim());
        }
    }

    static boolean isTimeoutEnabled() {
        return preferences().getBoolean(TIMEOUT_ENABLED_KEY, false);
    }

    static void setTimeoutEnabled(boolean enabled) {
        preferences().putBoolean(TIMEOUT_ENABLED_KEY, enabled);
    }

    static int getTimeoutSeconds() {
        return normalizeTimeoutSeconds(preferences().getInt(TIMEOUT_SECONDS_KEY, DEFAULT_TIMEOUT_SECONDS));
    }

    static void setTimeoutSeconds(int seconds) {
        preferences().putInt(TIMEOUT_SECONDS_KEY, normalizeTimeoutSeconds(seconds));
    }

    static int getBatchSize() {
        return normalizeChoice(preferences().getInt(BATCH_SIZE_KEY, DEFAULT_BATCH_SIZE), new int[]{1, 8, 32}, DEFAULT_BATCH_SIZE);
    }

    static void setBatchSize(int batchSize) {
        preferences().putInt(BATCH_SIZE_KEY, normalizeChoice(batchSize, new int[]{1, 8, 32}, DEFAULT_BATCH_SIZE));
    }

    static int getMaxSeqLength() {
        return normalizeChoice(preferences().getInt(MAX_SEQ_LENGTH_KEY, DEFAULT_MAX_SEQ_LENGTH), new int[]{64, 128, 256, 512}, DEFAULT_MAX_SEQ_LENGTH);
    }

    static void setMaxSeqLength(int maxSeqLength) {
        preferences().putInt(MAX_SEQ_LENGTH_KEY, normalizeChoice(maxSeqLength, new int[]{64, 128, 256, 512}, DEFAULT_MAX_SEQ_LENGTH));
    }

    static double getHateThreshold() {
        return normalizeThreshold(preferences().getDouble(HATE_THRESHOLD_KEY, DEFAULT_HATE_THRESHOLD));
    }

    static void setHateThreshold(double threshold) {
        preferences().putDouble(HATE_THRESHOLD_KEY, normalizeThreshold(threshold));
    }

    static boolean useCuda() {
        return preferences().getBoolean(USE_CUDA_KEY, true);
    }

    static void setUseCuda(boolean enabled) {
        preferences().putBoolean(USE_CUDA_KEY, enabled);
    }

    static String getHateLabelIds() {
        return preferences().get(HATE_LABEL_IDS_KEY, "");
    }

    static void setHateLabelIds(String value) {
        putOrRemove(HATE_LABEL_IDS_KEY, value);
    }

    static String getHateLabelNames() {
        return preferences().get(HATE_LABEL_NAMES_KEY, "");
    }

    static void setHateLabelNames(String value) {
        putOrRemove(HATE_LABEL_NAMES_KEY, value);
    }

    static File defaultModelsDirectory() {
        File exe = findCliExecutable();
        if (exe != null && exe.getParentFile() != null) {
            return new File(exe.getParentFile(), "models");
        }
        return new File(System.getProperty("user.home"), "HateSpeechDetector/models");
    }

    static String defaultLogFilePattern() {
        File logDir = defaultCaseLogDirectory();
        return new File(logDir, "hatespeech_YYYYMMDD_HHMMSS.log").getAbsolutePath();
    }

    static String defaultEvaluationFilePattern() {
        File logDir = defaultCaseLogDirectory();
        return new File(logDir, "evaluation_YYYYMMDD_HHMMSS.csv").getAbsolutePath();
    }

    private static File defaultCaseLogDirectory() {
        try {
            String moduleDir = Case.getCurrentCaseThrows().getModuleDirectory();
            return new File(moduleDir, "HateSpeechDetector");
        } catch (NoCurrentCaseException ex) {
            return new File(System.getProperty("user.home"), "HateSpeechDetector/logs");
        }
    }

    static File findCliExecutable() {
        String codeNameBase = "rs.ac.uns.ftn.digfor.hatespeech";
        String[] paths = {
            "modules/ext/hatespeech-bin/windows/hatespeech_cli_v1.exe",
            "modules/ext/hatespeech-bin/windows/hatespeech_cli.exe"
        };
        for (String path : paths) {
            File exe = InstalledFileLocator.getDefault().locate(path, codeNameBase, false);
            if (exe != null && exe.exists()) {
                return exe;
            }
        }
        return null;
    }

    static boolean isModelDownloadInProgress() {
        return modelDownloadInProgress;
    }

    static void setModelDownloadInProgress(boolean inProgress) {
        modelDownloadInProgress = inProgress;
    }

    private static int normalizeTimeoutSeconds(int seconds) {
        return seconds <= 0 ? DEFAULT_TIMEOUT_SECONDS : seconds;
    }

    private static int normalizeChoice(int value, int[] allowed, int fallback) {
        for (int allowedValue : allowed) {
            if (value == allowedValue) {
                return value;
            }
        }
        return fallback;
    }

    private static double normalizeThreshold(double threshold) {
        if (Double.isNaN(threshold)) {
            return DEFAULT_HATE_THRESHOLD;
        }
        return Math.max(0.0, Math.min(1.0, threshold));
    }

    private static void putOrRemove(String key, String value) {
        if (value == null || value.isBlank()) {
            preferences().remove(key);
        } else {
            preferences().put(key, value.trim());
        }
    }

    private static Preferences preferences() {
        return NbPreferences.forModule(HateSpeechGlobalSettings.class);
    }
}
