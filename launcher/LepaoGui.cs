using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

static class Program
{
    [STAThread]
    static void Main()
    {
        try
        {
            string repo = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
            string configPath = Path.Combine(repo, "config.json");
            if (!File.Exists(configPath))
                throw new InvalidOperationException("找不到配置: " + configPath);
            string python = ReadJsonString(File.ReadAllText(configPath), "python");
            if (string.IsNullOrEmpty(python))
                throw new InvalidOperationException("config.json 里没有 python");
            string pythonw = Path.Combine(Path.GetDirectoryName(python), "pythonw.exe");
            if (File.Exists(pythonw))
                python = pythonw;
            if (!File.Exists(python))
                throw new InvalidOperationException("找不到 Python: " + python);

            var start = new ProcessStartInfo();
            start.FileName = python;
            start.Arguments = "-m lepao.gui";
            start.WorkingDirectory = repo;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.EnvironmentVariables["PYTHONPATH"] = repo;
            start.EnvironmentVariables["PYTHONUTF8"] = "1";
            start.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            Process.Start(start);
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "自动跑", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    static string ReadJsonString(string text, string key)
    {
        int mark = text.IndexOf("\"" + key + "\"", StringComparison.OrdinalIgnoreCase);
        if (mark < 0)
            return null;
        int colon = text.IndexOf(':', mark);
        if (colon < 0)
            return null;
        int open = text.IndexOf('"', colon + 1);
        int close = text.IndexOf('"', open + 1);
        if (open < 0 || close < 0)
            return null;
        return text.Substring(open + 1, close - open - 1).Replace("\\\\", "\\");
    }
}
