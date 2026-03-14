import { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import {
    Card,
    CardContent,
    CardHeader,
    Button,
    TextField,
    Grid,
    Alert,
    CircularProgress,
} from '@mui/material';
import { httpClient } from '../../dataProvider';
import { useNotify } from 'react-admin';

export const PromptEditor = ({ promptId }: { promptId?: string }) => {
    const [promptText, setPromptText] = useState('');
    const [notes, setNotes] = useState('');
    const [testInput, setTestInput] = useState('');
    const [testOutput, setTestOutput] = useState('');
    const [testing, setTesting] = useState(false);
    const notify = useNotify();

    useEffect(() => {
        if (promptId) {
            // Load existing prompt
            const fetchPrompt = async () => {
                const auth = localStorage.getItem('auth');
                const session = JSON.parse(auth || '{}');
                const { data } = await httpClient.get(`/admin/prompts/${promptId}`);
                setPromptText(data.prompt_text);
                setNotes(data.notes || '');
            };
            fetchPrompt();
        }
    }, [promptId]);

    const handleTest = async () => {
        setTesting(true);
        try {
            const auth = localStorage.getItem('auth');
            const session = JSON.parse(auth || '{}');
            const { data } = await httpClient.post('/admin/prompts/test', {
                prompt_text: promptText,
                sample_text: testInput
            });
            setTestOutput(data.output);
            notify('Test completed successfully');
        } catch (error) {
            notify('Test failed', { type: 'error' });
        }
        setTesting(false);
    };

    const handleSave = async () => {
        try {
            const auth = localStorage.getItem('auth');
            const session = JSON.parse(auth || '{}');
            await httpClient.post('/admin/prompts', {
                prompt_text: promptText,
                notes
            });
            notify('Prompt saved as new version');
        } catch (error) {
            notify('Failed to save prompt', { type: 'error' });
        }
    };

    return (
        <Grid container spacing={2} style={{ padding: 20 }}>
            <Grid item xs={12}>
                <Card>
                    <CardHeader title="Humanizer Prompt Editor" />
                    <CardContent>
                        <Editor
                            height="400px"
                            defaultLanguage="markdown"
                            value={promptText}
                            onChange={(value) => setPromptText(value || '')}
                            theme="vs-dark"
                            options={{
                                minimap: { enabled: false },
                                fontSize: 14,
                                wordWrap: 'on',
                            }}
                        />
                        <TextField
                            fullWidth
                            multiline
                            rows={2}
                            label="Version Notes"
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            style={{ marginTop: 16 }}
                        />
                    </CardContent>
                </Card>
            </Grid>

            <Grid item xs={12}>
                <Card>
                    <CardHeader title="Test Prompt" />
                    <CardContent>
                        <TextField
                            fullWidth
                            multiline
                            rows={4}
                            label="Sample AI Output (to humanize)"
                            value={testInput}
                            onChange={(e) => setTestInput(e.target.value)}
                            style={{ marginBottom: 16 }}
                        />
                        <Button
                            variant="outlined"
                            onClick={handleTest}
                            disabled={testing || !promptText || !testInput}
                        >
                            {testing ? <CircularProgress size={24} /> : 'Test Prompt'}
                        </Button>
                        {testOutput && (
                            <Alert severity="success" style={{ marginTop: 16 }}>
                                <TextField
                                    fullWidth
                                    multiline
                                    rows={6}
                                    label="Humanized Output"
                                    value={testOutput}
                                    InputProps={{ readOnly: true }}
                                />
                            </Alert>
                        )}
                    </CardContent>
                </Card>
            </Grid>

            <Grid item xs={12}>
                <Button variant="contained" onClick={handleSave} style={{ marginRight: 8 }}>
                    Save as New Version
                </Button>
            </Grid>
        </Grid>
    );
};
