import { StatusBar } from "expo-status-bar";
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Button,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
import * as FileSystem from "expo-file-system";
import * as SecureStore from "expo-secure-store";

type Summary = {
  inventory?: {
    files_inventoried?: number;
    duplicate_groups?: number;
    recoverable_bytes?: number;
  };
  outlook?: {
    account?: string;
    mail?: number;
    calendar?: number;
    tasks?: number;
    contacts?: number;
  };
  outlook_actions?: {
    total?: number;
    approved?: number;
    applied?: number;
  };
  recovery?: {
    groups?: number;
    approved_groups?: number;
  };
};

const bytes = (value?: number): string => {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || number <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = number;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit ? 1 : 0)} ${units[unit]}`;
};

export default function App() {
  const [apiBase, setApiBase] = useState("");
  const [pairingToken, setPairingToken] = useState("");
  const [settingsStatus, setSettingsStatus] = useState<"loading" | "ready" | "unavailable">("loading");
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [driveSource, setDriveSource] = useState("D:\\");
  const [icloudSource, setIcloudSource] = useState("");
  const [message, setMessage] = useState("Connect to your Windows companion API.");
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      SecureStore.getItemAsync("jf-life-api-base"),
      SecureStore.getItemAsync("jf-life-pairing-token"),
      SecureStore.getItemAsync("jf-life-drive-source"),
      SecureStore.getItemAsync("jf-life-icloud-source"),
    ]).then(([savedApi, savedToken, savedDrive, savedICloud]) => {
      if (!active) return;
      setApiBase(savedApi ?? "");
      setPairingToken(savedToken ?? "");
      setDriveSource(savedDrive ?? "D:\\");
      setIcloudSource(savedICloud ?? "");
      setSettingsStatus("ready");
    }).catch(() => {
      if (active) setSettingsStatus("unavailable");
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (settingsStatus !== "ready") return;
    SecureStore.setItemAsync("jf-life-api-base", apiBase).catch(() => undefined);
  }, [apiBase, settingsStatus]);

  useEffect(() => {
    if (settingsStatus !== "ready") return;
    SecureStore.setItemAsync("jf-life-pairing-token", pairingToken).catch(() => undefined);
  }, [pairingToken, settingsStatus]);

  useEffect(() => {
    if (settingsStatus !== "ready") return;
    SecureStore.setItemAsync("jf-life-drive-source", driveSource).catch(() => undefined);
  }, [driveSource, settingsStatus]);

  useEffect(() => {
    if (settingsStatus !== "ready") return;
    SecureStore.setItemAsync("jf-life-icloud-source", icloudSource).catch(() => undefined);
  }, [icloudSource, settingsStatus]);

  const call = async <T,>(
    path: string,
    init: RequestInit = {}
  ): Promise<T> => {
    const baseUrl = apiBase.trim().replace(/\/+$/, "");
    if (!baseUrl) throw new Error("Enter the companion address shown on your Windows PC.");
    const headers = new Headers(init.headers);
    headers.set("Content-Type", "application/json");
    if (pairingToken.trim()) {
      headers.set("Authorization", `Bearer ${pairingToken.trim()}`);
    }
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers,
    });
    const body = await response.json();
    if (!response.ok || body.ok === false) {
      throw new Error(body.error || body.stderr || "Companion request failed.");
    }
    return body as T;
  };

  const run = async (label: string, path: string, body?: object) => {
    setLoading(true);
    setMessage(`${label}...`);
    try {
      const result = await call<{ summary?: Summary; stdout?: string }>(path, {
        method: "POST",
        body: JSON.stringify(body || {}),
      });
      if (result.summary) setSummary(result.summary);
      setMessage(`${label} complete.`);
    } catch (error) {
      setMessage(`${label} failed: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const sourceSpecs = () => {
    const sources: string[] = [];
    if (driveSource.trim()) sources.push(`DriveD=${driveSource.trim()}`);
    if (icloudSource.trim()) sources.push(`iCloud=${icloudSource.trim()}`);
    return sources;
  };

  const runInventory = () => run("Inventory", "/run/inventory", {
    sources: sourceSpecs(),
  });

  const publishLibrary = () => {
    Alert.alert(
      "Publish JF LIFE library",
      "This commits and pushes selected sources to the private GitHub repository. Continue only after review.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Publish",
          style: "destructive",
          onPress: () => run("Publish library", "/run/library-publish", {
            sources: sourceSpecs(),
            publish_confirmed: "PUBLISH_JF_LIFE",
          }),
        },
      ]
    );
  };

  const uploadPhoneFiles = async () => {
    try {
      const picked = await DocumentPicker.getDocumentAsync({
        type: "*/*",
        multiple: true,
        copyToCacheDirectory: true,
      });
      if (picked.canceled) return;
      setLoading(true);
      for (const asset of picked.assets) {
        if ((asset.size || 0) > 95 * 1024 * 1024) {
          throw new Error(`${asset.name} is larger than 95 MB.`);
        }
        const base64 = await FileSystem.readAsStringAsync(asset.uri, {
          encoding: FileSystem.EncodingType.Base64,
        });
        await call("/run/upload", {
          method: "POST",
          body: JSON.stringify({
            name: asset.name,
            relative_path: asset.name,
            size_bytes: asset.size || 0,
            mime_type: asset.mimeType || "application/octet-stream",
            base64,
          }),
        });
      }
      setMessage(`Uploaded ${picked.assets.length} file(s) to private JF LIFE state.`);
    } catch (error) {
      setMessage(`Upload failed: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const refreshSummary = async () => {
    setLoading(true);
    try {
      const result = await call<{ summary: Summary }>("/state/summary");
      setSummary(result.summary);
      setMessage("Summary refreshed.");
    } catch (error) {
      setMessage(`Refresh failed: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!autoRefresh || !apiBase.trim() || !pairingToken.trim()) return;
    const timer = setInterval(() => {
      refreshSummary().catch(() => undefined);
    }, 20000);
    return () => clearInterval(timer);
  }, [autoRefresh, apiBase, pairingToken]);

  const verifyPairing = async () => {
    setLoading(true);
    try {
      await call("/pairing/verify", {
        method: "POST",
        body: JSON.stringify({ pairing_token: pairingToken.trim() }),
      });
      setMessage("Pairing token verified.");
      await refreshSummary();
    } catch (error) {
      setMessage(`Pairing failed: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>JF LIFE</Text>
        <Text style={styles.subtitle}>
          iPhone-first app linked to your Windows companion
        </Text>

        {settingsStatus === "loading" && <Text style={styles.message}>Loading saved settings…</Text>}
        {settingsStatus === "unavailable" && (
          <Text style={styles.message}>Saved settings are unavailable. Changes will only apply for this session.</Text>
        )}
        <TextInput
          style={styles.input}
          value={apiBase}
          onChangeText={setApiBase}
          editable={settingsStatus !== "loading"}
          autoCapitalize="none"
          placeholder="http://192.168.x.x:8712"
          placeholderTextColor="#94a3b8"
        />
        <TextInput
          style={styles.input}
          value={pairingToken}
          onChangeText={setPairingToken}
          editable={settingsStatus !== "loading"}
          secureTextEntry
          autoCapitalize="none"
          placeholder="Pairing token from Windows companion"
          placeholderTextColor="#94a3b8"
        />
        <TextInput
          style={styles.input}
          value={driveSource}
          onChangeText={setDriveSource}
          editable={settingsStatus !== "loading"}
          autoCapitalize="none"
          placeholder="D:\ or JF external drive path"
          placeholderTextColor="#94a3b8"
        />
        <TextInput
          style={styles.input}
          value={icloudSource}
          onChangeText={setIcloudSource}
          editable={settingsStatus !== "loading"}
          autoCapitalize="none"
          placeholder="Windows iCloud JF LIFE folder (optional)"
          placeholderTextColor="#94a3b8"
        />
        <View style={styles.row}>
          <Button title="Verify Pairing" onPress={verifyPairing} />
          <Button title="Refresh" onPress={refreshSummary} />
        </View>
        <View style={styles.row}>
          <Text style={styles.item}>Live updates every 20s</Text>
          <Switch value={autoRefresh} onValueChange={setAutoRefresh} />
        </View>
        <Text style={styles.message}>{message}</Text>
        {loading ? <ActivityIndicator color="#f0cc73" /> : null}

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Run companion actions</Text>
          <View style={styles.row}>
            <Button title="Inventory" onPress={runInventory} />
            <Button title="Recovery plan" onPress={() => run("Recovery plan", "/run/recovery-plan")} />
          </View>
          <View style={styles.row}>
            <Button title="Outlook inventory" onPress={() => run("Outlook inventory", "/run/outlook-inventory")} />
            <Button title="Outlook plan" onPress={() => run("Outlook plan", "/run/outlook-plan")} />
          </View>
          <View style={styles.row}>
            <Button title="Outlook apply" onPress={() => run("Outlook apply", "/run/outlook-apply", { apply: true })} />
            <Button title="Dashboard" onPress={() => run("Dashboard", "/run/dashboard")} />
          </View>
          <View style={styles.row}>
            <Button title="Publish library" onPress={publishLibrary} />
          </View>
          <View style={styles.row}>
            <Button title="Upload iPhone/iCloud files" onPress={uploadPhoneFiles} />
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Summary</Text>
          <Text style={styles.item}>
            Files: {summary?.inventory?.files_inventoried ?? 0}
          </Text>
          <Text style={styles.item}>
            Duplicate groups: {summary?.inventory?.duplicate_groups ?? 0}
          </Text>
          <Text style={styles.item}>
            Recoverable: {bytes(summary?.inventory?.recoverable_bytes)}
          </Text>
          <Text style={styles.item}>
            Outlook account: {summary?.outlook?.account || "Not connected"}
          </Text>
          <Text style={styles.item}>
            Mail/Tasks/Contacts: {summary?.outlook?.mail ?? 0} /{" "}
            {summary?.outlook?.tasks ?? 0} / {summary?.outlook?.contacts ?? 0}
          </Text>
          <Text style={styles.item}>
            Approved Outlook actions: {summary?.outlook_actions?.approved ?? 0}
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#111827" },
  content: { padding: 20, gap: 10 },
  title: { color: "#f9fafb", fontSize: 30, fontWeight: "700" },
  subtitle: { color: "#cbd5e1", marginBottom: 10 },
  input: {
    borderWidth: 1,
    borderColor: "#4b5563",
    backgroundColor: "#1f2937",
    color: "#f9fafb",
    borderRadius: 8,
    padding: 10,
  },
  row: { flexDirection: "row", gap: 10, justifyContent: "space-between", marginVertical: 6 },
  message: { color: "#f0cc73", marginVertical: 8 },
  section: {
    marginTop: 12,
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#4b5563",
    backgroundColor: "#1f2937",
    gap: 6,
  },
  sectionTitle: { color: "#f9fafb", fontSize: 18, fontWeight: "600" },
  item: { color: "#e5e7eb" },
});
