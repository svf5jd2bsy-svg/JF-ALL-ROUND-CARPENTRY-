import { StatusBar } from "expo-status-bar";
import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Button,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";

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
  const [apiBase, setApiBase] = useState("http://192.168.0.100:8712");
  const [pairingToken, setPairingToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [message, setMessage] = useState("Connect to your Windows companion API.");
  const [summary, setSummary] = useState<Summary | null>(null);

  const authHeaders = useMemo(
    () =>
      pairingToken.trim()
        ? { Authorization: `Bearer ${pairingToken.trim()}` }
        : {},
    [pairingToken]
  );

  const call = async <T,>(
    path: string,
    init: RequestInit = {}
  ): Promise<T> => {
    const response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init.headers || {}),
        ...authHeaders,
      },
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
    if (!autoRefresh || !pairingToken.trim()) return;
    const timer = setInterval(() => {
      refreshSummary().catch(() => undefined);
    }, 20000);
    return () => clearInterval(timer);
  }, [autoRefresh, pairingToken]);

  const verifyPairing = async () => {
    setLoading(true);
    try {
      await call("/pairing/verify", {
        method: "POST",
        headers: {},
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

        <TextInput
          style={styles.input}
          value={apiBase}
          onChangeText={setApiBase}
          autoCapitalize="none"
          placeholder="http://192.168.x.x:8712"
          placeholderTextColor="#94a3b8"
        />
        <TextInput
          style={styles.input}
          value={pairingToken}
          onChangeText={setPairingToken}
          autoCapitalize="none"
          placeholder="Pairing token from Windows companion"
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
            <Button title="Inventory" onPress={() => run("Inventory", "/run/inventory", {})} />
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
