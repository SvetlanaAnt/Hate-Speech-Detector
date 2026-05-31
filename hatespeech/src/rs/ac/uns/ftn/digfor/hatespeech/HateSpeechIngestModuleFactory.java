package rs.ac.uns.ftn.digfor.hatespeech;

import org.openide.util.NbBundle;
import org.openide.util.lookup.ServiceProvider;
import org.sleuthkit.autopsy.ingest.DataSourceIngestModule;
import org.sleuthkit.autopsy.ingest.IngestModuleFactory;
import org.sleuthkit.autopsy.ingest.IngestModuleGlobalSettingsPanel;
import org.sleuthkit.autopsy.ingest.IngestModuleIngestJobSettings;
import org.sleuthkit.autopsy.ingest.IngestModuleIngestJobSettingsPanel;

@ServiceProvider(service = IngestModuleFactory.class)
public class HateSpeechIngestModuleFactory implements IngestModuleFactory{
    
    private static final String VERSION_NUMBER = "1.0.0";
    
    /**
     * Returns the localized module name.
     */
    static String getModuleName() {
        return NbBundle.getMessage(
                HateSpeechIngestModuleFactory.class,
                "HateSpeechIngestModuleFactory.moduleName"
        );
    }

    /**
     * Display name shown in the UI.
     */
    @Override
    public String getModuleDisplayName() {
        return getModuleName();
    }

    /**
     * Short module description shown in the UI.
     */
    @Override
    public String getModuleDescription() {
        return NbBundle.getMessage(
                HateSpeechIngestModuleFactory.class,
                "HateSpeechIngestModuleFactory.moduleDescription"
        );
    }

    /**
     * Module version string.
     */
    @Override
    public String getModuleVersionNumber() {
        return VERSION_NUMBER;
    }

    /**
     * Indicates whether a global settings panel is provided.
     */
    @Override
    public boolean hasGlobalSettingsPanel() {
        return true;
    }

    /**
     * Returns the global settings panel.
     */
    @Override
    public IngestModuleGlobalSettingsPanel getGlobalSettingsPanel() {
        return new HateSpeechGlobalSettingsPanel();
    }

    /**
     * Returns default per-job ingest settings.
     */
    @Override
    public IngestModuleIngestJobSettings getDefaultIngestJobSettings() {
        return new HateSpeechIngestJobSettings();
    }

    /**
     * Indicates whether a per-job settings panel is available.
     */
    @Override
    public boolean hasIngestJobSettingsPanel() {
        return true;
    }

    /**
     * Creates the per-job settings panel for this module.
     */
    @Override
    public IngestModuleIngestJobSettingsPanel getIngestJobSettingsPanel(IngestModuleIngestJobSettings settings) {
        if (!(settings instanceof HateSpeechIngestJobSettings)) {
            throw new IllegalArgumentException(
                    "Expected settings argument to be instanceof HateSpeechIngestJobSettings"
            );
        }
        return HateSpeechIngestJobSettingsPanel.create((HateSpeechIngestJobSettings) settings);
    }

    /**
     * Indicates this factory provides a data source ingest module.
     */
    @Override
    public boolean isDataSourceIngestModuleFactory() {
        return true;
    }

    /**
     * Creates a new data source ingest module instance.
     */
    @Override
    public DataSourceIngestModule createDataSourceIngestModule(IngestModuleIngestJobSettings settings) {
        if (!(settings instanceof HateSpeechIngestJobSettings)) {
            throw new IllegalArgumentException(
                    "Expected settings argument to be instanceof HateSpeechIngestJobSettings"
            );
        }
        return new HateSpeechDataSourceIngestModule((HateSpeechIngestJobSettings) settings);
    }

    /**
     * Indicates this factory does not provide a file ingest module.
     */
    @Override
    public boolean isFileIngestModuleFactory() {
        return false; 
    }

}
