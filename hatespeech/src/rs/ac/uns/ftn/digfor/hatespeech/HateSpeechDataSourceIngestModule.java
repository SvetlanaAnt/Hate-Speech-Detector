package rs.ac.uns.ftn.digfor.hatespeech;

import com.fasterxml.jackson.core.JsonProcessingException;
import java.io.IOException;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.logging.Level;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.sleuthkit.autopsy.casemodule.Case;
import org.sleuthkit.autopsy.casemodule.NoCurrentCaseException;
import org.sleuthkit.autopsy.coreutils.Logger;
import org.sleuthkit.autopsy.ingest.DataSourceIngestModule;
import org.sleuthkit.autopsy.ingest.DataSourceIngestModuleProgress;
import org.sleuthkit.autopsy.ingest.IngestJobContext;
import org.sleuthkit.autopsy.ingest.IngestModule;
import org.sleuthkit.autopsy.ingest.IngestMessage;
import org.sleuthkit.autopsy.ingest.IngestServices;
import org.sleuthkit.datamodel.BlackboardArtifact;
import org.sleuthkit.datamodel.BlackboardAttribute;
import org.sleuthkit.datamodel.Content;
import org.sleuthkit.datamodel.DataArtifact;
import org.sleuthkit.datamodel.SleuthkitCase;
import org.sleuthkit.datamodel.TskCoreException;
import org.sleuthkit.datamodel.Blackboard.BlackboardException;
import org.sleuthkit.datamodel.Blackboard;
import org.sleuthkit.datamodel.Score;
import org.sleuthkit.datamodel.AnalysisResultAdded;
import org.openide.util.Exceptions;
import org.sleuthkit.autopsy.ingest.ModuleDataEvent;

public class HateSpeechDataSourceIngestModule implements DataSourceIngestModule {

    private final HateSpeechIngestJobSettings settings;
    private IngestJobContext context = null;
   
    // Blackboard artifact types and attributes used by this module.
    private BlackboardArtifact.Type HATE_HIT_TYPE;
    private BlackboardAttribute.Type ATTR_MESSAGE_TYPE;         // Source: Email / WhatsApp / Viber / ...
    private BlackboardAttribute.Type ATTR_MATCHED_TEXT;         // Email/message snippet
    private BlackboardAttribute.Type ATTR_HATE_SCORE;           // Model score
    
    private static final int MAX_SNIPPET_CHARS = 250;           // Max snippet length
    private static final long DEFAULT_HATE_SPEECH_TIMEOUT_SECONDS = 120;
    private static final String TIMESTAMP_PLACEHOLDER = "YYYYMMDD_HHMMSS";
    
    /**
     * Creates a data source ingest module with the provided job settings.
     */
    public HateSpeechDataSourceIngestModule(HateSpeechIngestJobSettings hateSpeechIngestJobSettings) {
        this.settings = hateSpeechIngestJobSettings;
    }

    /**
     * Registers custom blackboard artifacts/attributes for this module.
     */
    @Override
    public void startUp(IngestJobContext context) throws IngestModuleException {
        Logger logger = IngestServices.getInstance().getLogger(HateSpeechIngestModuleFactory.getModuleName());
        this.context = context; 
        try {
            SleuthkitCase skCase = Case.getCurrentCaseThrows().getSleuthkitCase();
            Blackboard blackboard = skCase.getBlackboard();
            
            // Custom artifact type (Results tree -> Analysis Results -> Hate Speech Hit)
            HATE_HIT_TYPE = blackboard.getOrAddArtifactType(
                "TSK_HATE_SPEECH_HIT",
                "Hate Speech Hit",
                BlackboardArtifact.Category.ANALYSIS_RESULT
            );
            ATTR_MESSAGE_TYPE = blackboard.getOrAddAttributeType(
                    "TSK_HATE_MESSAGE_TYPE",
                    BlackboardAttribute.TSK_BLACKBOARD_ATTRIBUTE_VALUE_TYPE.STRING,
                    "01 Message Type"
            );
            ATTR_MATCHED_TEXT = blackboard.getOrAddAttributeType(
                    "TSK_HATE_MATCHED_TEXT",
                    BlackboardAttribute.TSK_BLACKBOARD_ATTRIBUTE_VALUE_TYPE.STRING,
                    "02 Matched Text"
            );            
            ATTR_HATE_SCORE = blackboard.getOrAddAttributeType(
                    "TSK_HATE_SCORE",
                    BlackboardAttribute.TSK_BLACKBOARD_ATTRIBUTE_VALUE_TYPE.DOUBLE,
                    "03 Hate Score"
            );
            logger.log(Level.INFO, "Registered custom artifact/attribute types in blackboard.");
        } catch (NoCurrentCaseException | BlackboardException ex) {
            logger.log(Level.SEVERE, "Failed to register custom artifact/attribute types in blackboard.", ex);
            throw new IngestModuleException("Failed to register custom artifact/attribute types", ex);
        }
    }

    /**
     * Collects email/message artifacts, runs the ML model, and posts analysis results.
     */
    @Override
    public ProcessResult process(Content dataSource, DataSourceIngestModuleProgress progressBar) {
        Logger logger = IngestServices.getInstance().getLogger(HateSpeechIngestModuleFactory.getModuleName());
        try {
            if (HateSpeechGlobalSettings.isModelDownloadInProgress()) {
                String message = "Hate Speech Detector model download is in progress. Wait for the download to finish, then rerun ingest.";
                logger.log(Level.WARNING, message);
                postMessageToUser(IngestMessage.MessageType.WARNING, message);
                return IngestModule.ProcessResult.ERROR;
            }

            SleuthkitCase skCase = Case.getCurrentCaseThrows().getSleuthkitCase();

            // Get email artifacts (global for case) [TSK_EMAIL_MSG]
            List<BlackboardArtifact> emailArtifacts = skCase.getBlackboardArtifacts(BlackboardArtifact.ARTIFACT_TYPE.TSK_EMAIL_MSG);
            // Get message artifacts (global for case) [TSK_MESSAGE]
            List<BlackboardArtifact> messageArtifacts = skCase.getBlackboardArtifacts(BlackboardArtifact.ARTIFACT_TYPE.TSK_MESSAGE);
           
            // Artifacts may be missing if upstream modules have not finished yet.
            boolean noEmails = (emailArtifacts == null || emailArtifacts.isEmpty());
            boolean noMessages = (messageArtifacts == null || messageArtifacts.isEmpty());
            boolean includeEmail = (settings == null) || settings.includeEmail();
            boolean includeSmsMms = (settings == null) || settings.includeSmsMms();
            boolean includeWhatsApp = (settings == null) || settings.includeWhatsApp();
            boolean includeViber = (settings == null) || settings.includeViber();
            boolean includeTelegram = (settings == null) || settings.includeTelegram();
            boolean includeOtherMessages = (settings == null) || settings.includeOtherMessages();
            boolean processEmails = !noEmails && includeEmail;
            boolean processMessages = !noMessages && (includeSmsMms || includeWhatsApp || includeViber || includeTelegram || includeOtherMessages);
            if (!processEmails && !processMessages) {
                String message = "No selected sources or artifacts found (TSK_EMAIL_MSG / TSK_MESSAGE). Enable Email Parser / Android Analyzer / iOS Analyzer / relevant modules and rerun.";
                logger.log(Level.INFO, message);
                postMessageToUser(IngestMessage.MessageType.INFO, message);
                return IngestModule.ProcessResult.OK;
            }
            
            int totalArtifacts = (processEmails ? emailArtifacts.size() : 0) + (processMessages ? messageArtifacts.size() : 0);
            
            // Determinate progress by artifact count (fast phase: collecting text)
            progressBar.switchToDeterminate(totalArtifacts);
            
            // Build input for the Python CLI tool
            List<Map<String, Object>> items = new ArrayList<>();
            // Map artifactId -> artifact (email + message)
            Map<Long, BlackboardArtifact> artifactsById = new HashMap<>();
            int progress = 0;
            int itemIdCounter = 0;
            if (processEmails) {
                for(BlackboardArtifact email : emailArtifacts) {
                
                    // User canceled the ingest job
                    if (context != null && context.dataSourceIngestIsCancelled()) {
                        logger.log(Level.INFO, "Ingest cancelled by user.");
                        return IngestModule.ProcessResult.OK;
                    }

                    // Extract id, body, and subject (if any)
                    Long artifactId = email.getArtifactID();
                    artifactsById.put(artifactId, email);
                    String body = getAttributeString(email, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_EMAIL_CONTENT_PLAIN);
                    String subject = getAttributeString(email, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_SUBJECT);
                    // logger.log(Level.INFO, "EMAIL artifact id={0}, subject={1}, body={2}", new Object[]{ artifactId, truncateText(subject, MAX_SNIPPET_CHARS), truncateText(body, MAX_SNIPPET_CHARS) });
                         
                    if (!subject.isBlank()) {
                        Map<String, Object> item = new HashMap<>();
                        item.put("id", itemIdCounter++);
                        item.put("id_artifact", artifactId);
                        item.put("text", subject);
                        item.put("message_type", "email");
                        items.add(item);
                    }
                    if (!body.isBlank()) {
                        Map<String, Object> item = new HashMap<>();
                        item.put("id", itemIdCounter++);
                        item.put("id_artifact", artifactId);
                        item.put("text", body);
                        item.put("message_type", "email");
                        items.add(item);
                    }
                    progressBar.progress(++progress);
                }
            }
            
            if (processMessages) {
                for(BlackboardArtifact msg : messageArtifacts) {
                    // User canceled the ingest job
                    if (context != null && context.dataSourceIngestIsCancelled()) {
                        logger.log(Level.INFO, "Ingest cancelled by user.");
                        return IngestModule.ProcessResult.OK;
                    }
                    
                    Long artifactId = msg.getArtifactID();
                    artifactsById.put(artifactId, msg);
                    String text = getAttributeString(msg, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_TEXT);
                    String msgType = getAttributeString(msg, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_MESSAGE_TYPE); // e.g. viber, whatsapp, telegram...
                    if (msgType.isBlank()) {
                        msgType = "message";
                    }
                    if (!shouldIncludeMessageType(
                            msgType,
                            includeSmsMms,
                            includeWhatsApp,
                            includeViber,
                            includeTelegram,
                            includeOtherMessages
                    )) {
                        progressBar.progress(++progress);
                        continue;
                    }
                    // logger.log(Level.INFO, "MESSAGE artifact id={0}, type={1}, text={2}", new Object[]{ artifactId, msgType, truncateText(text, MAX_SNIPPET_CHARS) });
                    
                    if (!text.isBlank()) {
                        Map<String, Object> item = new HashMap<>();
                        item.put("id", itemIdCounter++);
                        item.put("id_artifact", artifactId);
                        item.put("text", text);
                        item.put("message_type", msgType);
                        items.add(item);
                    }
                    progressBar.progress(++progress);
                }
            }
            
            if (items.isEmpty()) {
                String message = "Email/message artifacts exist, but no text was found to analyze.";
                logger.log(Level.INFO, message);
                postMessageToUser(IngestMessage.MessageType.INFO, message);
                return IngestModule.ProcessResult.OK;
            }
            
            // PYTHON (subprocess)
            // Payload for the Python CLI tool
            Map<String, Object> payload = new HashMap<>();
            payload.put("items", items);
            
            ObjectMapper mapper = new ObjectMapper();
            String jsonInput;
            try {
                jsonInput = mapper.writeValueAsString(payload);
            } catch (JsonProcessingException ex) {
                String message = "Failed to serialize JSON payload";
                logger.log(Level.SEVERE, message, ex);
                postMessageToUser(IngestMessage.MessageType.ERROR, message);
                return IngestModule.ProcessResult.ERROR;
            }
            
            // Long phase: inference in the Python/EXE process
            progressBar.switchToIndeterminate();

            String jsonOutput;
            try {
                if (HateSpeechGlobalSettings.isTimeoutEnabled()) {
                    long timeoutSeconds = HateSpeechGlobalSettings.getTimeoutSeconds();
                    if (timeoutSeconds <= 0) {
                        timeoutSeconds = DEFAULT_HATE_SPEECH_TIMEOUT_SECONDS;
                    }
                    jsonOutput = callPythonHateSpeechWithTimeout(jsonInput, timeoutSeconds);
                } else {
                    jsonOutput = callPythonHateSpeech(jsonInput);
                }
            } catch (IOException | InterruptedException ex) {
                String message = "Failed to call python hate speech module";
                logger.log(Level.SEVERE, message, ex);
                postMessageToUser(IngestMessage.MessageType.ERROR, message);
                return IngestModule.ProcessResult.ERROR;
            }

            JsonNode root;
            try {
                root = mapper.readTree(jsonOutput);
            } catch (JsonProcessingException ex) {
                String message = "Failed to parse json output";
                logger.log(Level.SEVERE, message, ex);
                postMessageToUser(IngestMessage.MessageType.ERROR, message);
                return IngestModule.ProcessResult.ERROR;
            }
            
            JsonNode outItems = (root != null) ? root.get("items") : null;
            if (outItems == null || !outItems.isArray()) {
                String message = "Python output missing 'items' array.";
                logger.log(Level.SEVERE, message + "Output was: {0}", jsonOutput);
                postMessageToUser(IngestMessage.MessageType.ERROR, message);
                return IngestModule.ProcessResult.ERROR;
            }
            
             /* OUTPUT EXAMPLE
            {
                "id": 39,
                "id_artifact": 120,
                "text": "I appreciate your input, thank you.",
                "label_id": 0,
                "label_name": "normal",
                "is_hate_speech": false,
                "hate_score": 0.010008813429404035
            },
            {
                "id": 68,
                "id_artifact": 134,
                "text": "I hope you fail at everything you try. You are a stain on this group and we would be better without you.",
                "label_id": 1,
                "label_name": "hatespeech",
                "is_hate_speech": true,
                "hate_score": 0.663192957394956
            },
            */
            // Determinate progress by number of results
            int totalResults = outItems.size();
            if (totalResults > 0) {
                progressBar.switchToDeterminate(totalResults);
            }

            int resultsProgress = 0;
            Map<Long, MessageHit> hitsByMessage = new HashMap<>();
            for (JsonNode outItem : outItems) {
                if (totalResults > 0) {
                    progressBar.progress(++resultsProgress);
                }
                long msgId = outItem.get("id_artifact").asLong();
                boolean isHate = outItem.get("is_hate_speech").asBoolean(false);
                double hateScore = outItem.has("hate_score") ? outItem.get("hate_score").asDouble(0.0) : 0.0;

               if (!isHate) {
                   continue;
               }

                String rawText = outItem.has("text") ? outItem.get("text").asText("") : "";
                String snippet = truncateText(rawText, MAX_SNIPPET_CHARS);
                String messageType = outItem.has("message_type") ? outItem.get("message_type").asText("") : "";

                MessageHit hit = hitsByMessage.get(msgId);
                if (hit == null) {
                    hit = new MessageHit(msgId);
                    hitsByMessage.put(msgId, hit);
                }
                if (messageType != null && !messageType.isBlank()) {
                    hit.messageType = messageType;
                }
                if (hateScore > hit.maxScore) {
                    hit.maxScore = hateScore;
                    hit.snippet = snippet;
                } else if (hit.snippet == null || hit.snippet.isBlank()) {
                    hit.snippet = snippet;
                }
            }

            int hateHits = 0;
            List<BlackboardArtifact> artifactsToPost = new ArrayList<>();
            for (MessageHit hit : hitsByMessage.values()) {
                long msgId = hit.messageArtifactId;

                BlackboardArtifact srcArtifact = artifactsById.get(msgId);
                if (srcArtifact == null) {
                    String message = "No source artifact found for id_artifact=" + msgId;
                    logger.log(Level.WARNING, message);
                    postMessageToUser(IngestMessage.MessageType.WARNING, message);
                    continue;
                }

                logger.log(Level.INFO, "Creating analysis result artifact for detected hate speech.");

                // Attributes
                List<BlackboardAttribute> attrs = new ArrayList<>();
                String artifactPath = "";
                String sourcePath = "";
                try {
                    artifactPath = srcArtifact.getUniquePath();
                } catch (TskCoreException ex) {
                    logger.log(Level.FINE, "Failed to get artifact unique path for artifactId=" + msgId, ex);
                }
                try {
                    Content parent = srcArtifact.getParent();
                    if (parent != null) {
                        sourcePath = parent.getUniquePath();
                    }
                } catch (TskCoreException ex) {
                    logger.log(Level.FINE, "Failed to get source parent path for artifactId=" + msgId, ex);
                }
                // TSK_PATH = srcArtifact.getUniquePath() (path to the artifact itself)
                if (artifactPath != null && !artifactPath.isBlank()) {
                    attrs.add(new BlackboardAttribute(
                            BlackboardAttribute.ATTRIBUTE_TYPE.TSK_PATH,
                            HateSpeechIngestModuleFactory.getModuleName(),
                            artifactPath
                    ));
                }
                // TSK_PATH_SOURCE = srcArtifact.getParent().getUniquePath() (path to the source file, e.g., PST or DB)
                if (sourcePath != null && !sourcePath.isBlank()) {
                    attrs.add(new BlackboardAttribute(
                            BlackboardAttribute.ATTRIBUTE_TYPE.TSK_PATH_SOURCE,
                            HateSpeechIngestModuleFactory.getModuleName(),
                            sourcePath
                    ));
                }
                addMessageContextAttributes(srcArtifact, attrs, logger);
                attrs.add(new BlackboardAttribute(ATTR_HATE_SCORE, HateSpeechIngestModuleFactory.getModuleName(), hit.maxScore));
                attrs.add(new BlackboardAttribute(
                        new BlackboardAttribute.Type(BlackboardAttribute.ATTRIBUTE_TYPE.TSK_ASSOCIATED_ARTIFACT),
                        HateSpeechIngestModuleFactory.getModuleName(),
                        msgId
                ));
                if (hit.messageType != null && !hit.messageType.isBlank()) {
                    attrs.add(new BlackboardAttribute(ATTR_MESSAGE_TYPE, HateSpeechIngestModuleFactory.getModuleName(), hit.messageType));
                }
                if (hit.snippet != null && !hit.snippet.isBlank()) {
                    attrs.add(new BlackboardAttribute(ATTR_MATCHED_TEXT, HateSpeechIngestModuleFactory.getModuleName(), hit.snippet));
                }

                // Score mapping: adjust thresholds later if needed
                Score score = Score.SCORE_NOTABLE;

                String modelAlias = (settings != null) ? settings.getModelAlias() : "";
                if (modelAlias == null || modelAlias.isBlank()) {
                    modelAlias = "electra_hatexplain";
                }
                String justification = String.format(
                        Locale.ROOT,
                        "Model: %s; score: %.6f",
                        modelAlias,
                        hit.maxScore
                );
                AnalysisResultAdded added = srcArtifact.newAnalysisResult(
                        HATE_HIT_TYPE,
                        score,
                        "Hate speech detected",
                        HateSpeechIngestModuleFactory.getModuleName(),
                        justification,
                        attrs
                );

                BlackboardArtifact analysisResult = added.getAnalysisResult();
                artifactsToPost.add(analysisResult);
                hateHits++;        
            }
            
            // Post to blackboard (required for UI display and indexing)
            Blackboard blackboard = skCase.getBlackboard();
            try {
                 blackboard.postArtifacts(
                         artifactsToPost,
                         HateSpeechIngestModuleFactory.getModuleName(),
                         (context != null ? context.getJobId() : null)
                 );
            } catch (Blackboard.BlackboardException ex) {
                String message =  "Failed to post hate speech analysis results";
                logger.log(Level.WARNING, message, ex);
                postMessageToUser(IngestMessage.MessageType.ERROR, message);
            }

            String message =  "Hate Speech Detector: " + hateHits + " hit(s) added to Analysis Results → Hate Speech Hit.";
            logger.log(Level.INFO, message);
            postMessageToUser(IngestMessage.MessageType.DATA, message);
          
            return IngestModule.ProcessResult.OK;

        } catch (TskCoreException | NoCurrentCaseException ex) {
            String message =  "Failed to process TSK_EMAIL_MSG / TSK_MESSAGE artifacts";
            logger.log(Level.SEVERE, message, ex);
            postMessageToUser(IngestMessage.MessageType.ERROR, message);
            return IngestModule.ProcessResult.ERROR;
        }
    }


    /**
     * Called by Autopsy when the ingest job is shutting down.
     */
    @Override
    public void shutDown() {
        DataSourceIngestModule.super.shutDown();
    }
    
    /**
     * Executes the CLI with a hard timeout and returns the JSON output.
     */
    private String callPythonHateSpeechWithTimeout(String jsonInput, long timeoutSeconds) throws IOException, InterruptedException {
        ExecutorService executor = Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "hate-speech-cli");
            t.setDaemon(true);
            return t;
        });
        try {
            Future<String> future = executor.submit(() -> callPythonHateSpeech(jsonInput));
            try {
                return future.get(timeoutSeconds, TimeUnit.SECONDS);
            } catch (TimeoutException ex) {
                future.cancel(true);
                throw new IOException("Hate speech CLI timed out after " + timeoutSeconds + " seconds.", ex);
            } catch (ExecutionException ex) {
                Throwable cause = ex.getCause();
                if (cause instanceof IOException) {
                    throw (IOException) cause;
                }
                if (cause instanceof InterruptedException) {
                    throw (InterruptedException) cause;
                }
                throw new IOException("Failed to run hate speech CLI.", cause);
            }
        } finally {
            executor.shutdownNow();
        }
    }
    
    /**
     * Executes the CLI without a timeout and returns the JSON output.
     */
    private String callPythonHateSpeech(String jsonInput) throws IOException, InterruptedException {
        Logger logger = IngestServices.getInstance().getLogger(HateSpeechIngestModuleFactory.getModuleName());
        
        File exe = HateSpeechGlobalSettings.findCliExecutable();
        if(exe == null || !exe.exists()) {
            logger.log(Level.SEVERE, "Executable not found: hatespeech_cli_v1.exe");
            throw new IOException("Cannot find hatespeech_cli_v1.exe in module installation.");
        }
        logger.log(Level.INFO, "Executable found: {0}", exe.getAbsolutePath());

        String modelAlias = (settings != null) ? settings.getModelAlias() : "";
        if (modelAlias == null || modelAlias.isBlank()) {
            modelAlias = "electra_hatexplain";
        }
        String modelSource = (settings != null) ? settings.getModelSource() : HateSpeechIngestJobSettings.MODEL_SOURCE_AUTO;
        if (modelSource == null || modelSource.isBlank()) {
            modelSource = HateSpeechIngestJobSettings.MODEL_SOURCE_AUTO;
        }
        String modelsDir = HateSpeechGlobalSettings.getModelsDirectory();
        ProcessBuilder pb = new ProcessBuilder(
            exe.getAbsolutePath(),
            "--model-source", modelSource,
            "--models-dir", modelsDir
        );
        if ("all".equalsIgnoreCase(modelAlias)) {
            pb.command().add("--models");
            pb.command().add("all");
        } else {
            pb.command().add("--model");
            pb.command().add(modelAlias);
        }
        pb.command().add("--batch-size");
        pb.command().add(Integer.toString(HateSpeechGlobalSettings.getBatchSize()));
        pb.command().add("--max-seq-length");
        pb.command().add(Integer.toString(HateSpeechGlobalSettings.getMaxSeqLength()));
        pb.command().add("--hate-threshold");
        pb.command().add(String.format(Locale.ROOT, "%.2f", HateSpeechGlobalSettings.getHateThreshold()));
        if (HateSpeechGlobalSettings.useCuda()) {
            pb.command().add("--use-cuda");
        }
        appendRepeatedCliArgs(pb.command(), "--hate-label-id", HateSpeechGlobalSettings.getHateLabelIds());
        appendRepeatedCliArgs(pb.command(), "--hate-label-name", HateSpeechGlobalSettings.getHateLabelNames());
        File logFile = buildCaseLogFile(logger);
        if (logFile != null) {
            File evaluationLogFile = buildEvaluationLogFile(logFile);
            pb.command().add("--log-file");
            pb.command().add(logFile.getAbsolutePath());
            pb.command().add("--evaluation-log-file");
            pb.command().add(evaluationLogFile.getAbsolutePath());
            pb.command().add("--log-items");
            pb.command().add("--log-texts");
            logger.log(Level.INFO, "Hate speech CLI log file: {0}", logFile.getAbsolutePath());
            logger.log(Level.INFO, "Hate speech evaluation log file: {0}", evaluationLogFile.getAbsolutePath());
        }
        logger.log(Level.INFO, "ProcessBuilder created for hate speech CLI.");
        
        Process p = pb.start();
        logger.log(Level.INFO, "Hate speech CLI process started.");

        try (BufferedWriter w = new BufferedWriter(new OutputStreamWriter(p.getOutputStream(), StandardCharsets.UTF_8))) {
            w.write(jsonInput);
            logger.log(Level.INFO, "Sent JSON input to hate speech CLI.");
        }

        String stdout;
        try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
            stdout = r.lines().collect(Collectors.joining());
            logger.log(Level.INFO, "Collected stdout from hate speech CLI.");
        }

        String stderr;
        try (BufferedReader e = new BufferedReader(new InputStreamReader(p.getErrorStream(), StandardCharsets.UTF_8))) {
            logger.log(Level.INFO, "Collected stderr from hate speech CLI.");
            stderr = e.lines().collect(Collectors.joining("\n"));
        }

        int exit = p.waitFor();
        if (exit != 0) {
            logger.log(Level.SEVERE, "Hate speech CLI exited with non-zero status.");
            throw new IOException("Python error: " + stderr);
        }
        
        logger.log(Level.INFO, "Hate speech CLI finished.");
        return stdout;
    }

    private static void appendRepeatedCliArgs(List<String> command, String argName, String commaSeparatedValues) {
        if (commaSeparatedValues == null || commaSeparatedValues.isBlank()) {
            return;
        }
        String[] values = commaSeparatedValues.split(",");
        for (String rawValue : values) {
            String value = rawValue.trim();
            if (!value.isBlank()) {
                command.add(argName);
                command.add(value);
            }
        }
    }

    /**
     * Returns a trimmed snippet with an ellipsis if it exceeds maxChars.
     */
    private static String truncateText(String text, int maxChars) {
        if (text == null) {
            return "";
        }
        String trimmed = text.trim();
        if (trimmed.length() <= maxChars) {
            return trimmed;
        }
        return trimmed.substring(0, maxChars) + "...";
    }

    /**
     * Reads a string attribute value or display value from a blackboard artifact.
     */
    private static String getAttributeString(BlackboardArtifact artifact, BlackboardAttribute.ATTRIBUTE_TYPE attrType) throws TskCoreException {
        BlackboardAttribute attr = artifact.getAttribute(new BlackboardAttribute.Type(attrType));
        if (attr == null) {
            return "";
        }
        String value = attr.getValueString();
        if (value != null && !value.isBlank()) {
            return value;
        }
        String display = attr.getDisplayString();
        return (display != null) ? display : "";
    }
    
    /**
     * Filters message artifacts based on user-selected message source types.
     */
    private static boolean shouldIncludeMessageType(
            String msgType,
            boolean includeSmsMms,
            boolean includeWhatsApp,
            boolean includeViber,
            boolean includeTelegram,
            boolean includeOtherMessages
    ) {
        String normalized = (msgType == null) ? "" : msgType.toLowerCase(Locale.ROOT);
        boolean isWhatsApp = normalized.contains("whatsapp");
        boolean isViber = normalized.contains("viber");
        boolean isTelegram = normalized.contains("telegram");
        boolean isSmsMms = normalized.contains("sms") || normalized.contains("mms") || normalized.contains("android");
        if (isWhatsApp) {
            return includeWhatsApp;
        }
        if (isViber) {
            return includeViber;
        }
        if (isTelegram) {
            return includeTelegram;
        }
        if (isSmsMms) {
            return includeSmsMms;
        }
        return includeOtherMessages;
    }

    /**
     * Builds a per-case log file path for the CLI logs (if a case is open).
     */
    private static File buildCaseLogFile(Logger logger) {
        String timestamp = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss").format(LocalDateTime.now());
        return buildConfiguredFile(
                HateSpeechGlobalSettings.getLogFilePattern(),
                HateSpeechGlobalSettings.defaultLogFilePattern(),
                timestamp,
                logger
        );
    }

    /**
     * Builds the evaluation CSV path using the same timestamp as the main CLI log.
     */
    private static File buildEvaluationLogFile(File logFile) {
        String timestamp = extractTimestamp(logFile.getName());
        if (timestamp.isBlank()) {
            timestamp = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss").format(LocalDateTime.now());
        }
        return buildConfiguredFile(
                HateSpeechGlobalSettings.getEvaluationFilePattern(),
                HateSpeechGlobalSettings.defaultEvaluationFilePattern(),
                timestamp,
                null
        );
    }

    private static File buildConfiguredFile(String pattern, String defaultPattern, String timestamp, Logger logger) {
        String resolved = (pattern == null || pattern.isBlank())
                ? defaultPattern
                : pattern.trim();
        resolved = resolved.replace(TIMESTAMP_PLACEHOLDER, timestamp);
        File file = new File(resolved);
        File parent = file.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs() && logger != null) {
            logger.log(Level.WARNING, "Failed to create log directory: {0}", parent.getAbsolutePath());
        }
        return file;
    }

    private static String extractTimestamp(String fileName) {
        Matcher matcher = Pattern.compile("(\\d{8}_\\d{6})").matcher(fileName == null ? "" : fileName);
        return matcher.find() ? matcher.group(1) : "";
    }

    // Aggregated result per message (subject + body) to create a single artifact.
    private static class MessageHit {
        // Message artifact ID that this result is tied to.
        private final long messageArtifactId;
        // Highest hate score found for this message (subject or body).
        private double maxScore = 0.0;
        // Snippet that produced the detection.
        private String snippet;
        // Message type (email / WhatsApp / Viber / etc.).
        private String messageType;

        /**
         * Creates a hit container for the given message artifact id.
         */
        private MessageHit(long messageArtifactId) {
            this.messageArtifactId = messageArtifactId;
        }
    }

    /**
     * Posts a user-facing ingest message.
     */
    private void postMessageToUser(IngestMessage.MessageType messageType, String message){
        IngestServices.getInstance().postMessage(
            IngestMessage.createMessage(
                messageType,
                HateSpeechIngestModuleFactory.getModuleName(),
                message
            )
        );
    }
    
    /**
     * Copies relevant message/email context attributes from the source artifact.
     */
    private void addMessageContextAttributes(BlackboardArtifact srcArtifact, List<BlackboardAttribute> attrs, Logger logger) {
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_EMAIL_FROM, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_EMAIL_TO, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_EMAIL_CC, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_EMAIL_BCC, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_EMAIL_REPLYTO, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_SUBJECT, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_EMAIL_CONTENT_PLAIN, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_DATETIME_SENT, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_DATETIME_RCVD, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_MSG_ID, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_MSG_REPLY_ID, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_HEADERS, attrs, logger);
        
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_PHONE_NUMBER_FROM, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_PHONE_NUMBER_TO, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_DIRECTION, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_DATETIME, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_THREAD_ID, attrs, logger);
        addAttributeIfPresent(srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE.TSK_READ_STATUS, attrs, logger);
    }
    
    /**
     * Safely copies a single attribute if it exists on the source artifact.
     */
    private void addAttributeIfPresent(BlackboardArtifact srcArtifact, BlackboardAttribute.ATTRIBUTE_TYPE type, List<BlackboardAttribute> attrs, Logger logger) {
        try {
            BlackboardAttribute attr = srcArtifact.getAttribute(new BlackboardAttribute.Type(type));
            if (attr == null) {
                return;
            }
            BlackboardAttribute.TSK_BLACKBOARD_ATTRIBUTE_VALUE_TYPE valueType = attr.getValueType();
            switch (valueType) {
                case STRING:
                case JSON: {
                    String value = attr.getValueString();
                    if (value != null && !value.isBlank()) {
                        attrs.add(new BlackboardAttribute(type, HateSpeechIngestModuleFactory.getModuleName(), value));
                    }
                    break;
                }
                case INTEGER:
                    attrs.add(new BlackboardAttribute(type, HateSpeechIngestModuleFactory.getModuleName(), attr.getValueInt()));
                    break;
                case LONG:
                case DATETIME:
                    attrs.add(new BlackboardAttribute(type, HateSpeechIngestModuleFactory.getModuleName(), attr.getValueLong()));
                    break;
                case DOUBLE:
                    attrs.add(new BlackboardAttribute(type, HateSpeechIngestModuleFactory.getModuleName(), attr.getValueDouble()));
                    break;
                case BYTE: {
                    byte[] value = attr.getValueBytes();
                    if (value != null && value.length > 0) {
                        attrs.add(new BlackboardAttribute(type, HateSpeechIngestModuleFactory.getModuleName(), value));
                    }
                    break;
                }
                default:
                    break;
            }
        } catch (TskCoreException | IllegalArgumentException ex) {
            logger.log(Level.FINE, "Failed to copy attribute " + type.getLabel() + " from source artifact.", ex);
        }
    }
}
