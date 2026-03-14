import { useState, useEffect } from 'react';
import {
    Card,
    CardContent,
    Typography,
    Button,
    Grid,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    Paper,
    TextField,
    Box,
    Chip,
    CircularProgress,
    IconButton
} from '@mui/material';
import { useNotify, Title } from 'react-admin';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import SendIcon from '@mui/icons-material/Send';
import LaunchIcon from '@mui/icons-material/Launch';
import { httpClient } from '../../dataProvider';

export const BlogManager = () => {
    const [topics, setTopics] = useState<any[]>([]);
    const [posts, setPosts] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [suggestedTopic, setSuggestedTopic] = useState('');
    const notify = useNotify();

    const fetchContent = async () => {
        setLoading(true);
        try {
            const topicsRes = await httpClient.get('/admin/blog/topics');
            const postsRes = await httpClient.get('/admin/blog/posts');
            setTopics(Array.isArray(topicsRes.data) ? topicsRes.data : []);
            // Handle new paginated object structure { blogs: [], total: X ... }
            const postsData = postsRes.data.blogs || (Array.isArray(postsRes.data) ? postsRes.data : []);
            setPosts(postsData);
        } catch (error) {
            notify('Error fetching blog data', { type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchContent();
    }, []);

    const handleGenerateTopics = async () => {
        setGenerating(true);
        try {
            await httpClient.post('/admin/blog/generate-topics');
            notify('Generated 4 new topics!', { type: 'success' });
            fetchContent();
        } catch (error) {
            notify('Failed to generate topics', { type: 'error' });
        } finally {
            setGenerating(false);
        }
    };

    const handleApprove = async (id: string) => {
        try {
            await httpClient.post('/admin/blog/topics/approve', { topic_ids: [id] });
            notify('Topic approved! AI is writing the article...', { type: 'success' });
            fetchContent();
        } catch (error) {
            notify('Failed to approve topic', { type: 'error' });
        }
    };

    const handleSuggest = async () => {
        if (!suggestedTopic.trim()) return;
        setLoading(true);
        try {
            await httpClient.post('/admin/blog/suggest', { title: suggestedTopic });
            notify('Topic suggested! AI is writing it now.', { type: 'success' });
            setSuggestedTopic('');
            fetchContent();
        } catch (error) {
            notify('Failed to suggest topic', { type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    return (
        <Box sx={{ mt: 2 }}>
            <Title title="Blog Automation Control" />

            <Grid container spacing={3}>
                {/* Topic Generation Logic */}
                <Grid item xs={12} md={5}>
                    <Card sx={{ mb: 3, borderLeft: '4px solid #bc13fe' }}>
                        <CardContent>
                            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <AutoAwesomeIcon color="secondary" /> AI Topic Generator
                            </Typography>
                            <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
                                Ask the AI to brainstorm 4 SEO-optimized academic topics for your blog.
                            </Typography>
                            <Button
                                variant="contained"
                                color="secondary"
                                fullWidth
                                startIcon={generating ? <CircularProgress size={20} color="inherit" /> : <AutoAwesomeIcon />}
                                onClick={handleGenerateTopics}
                                disabled={generating || loading}
                            >
                                {generating ? 'Thinking...' : 'Generate 4 New Topics'}
                            </Button>
                        </CardContent>
                    </Card>

                    <Card sx={{ borderLeft: '4px solid #00f0ff' }}>
                        <CardContent>
                            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <SendIcon color="primary" /> Suggest a Topic
                            </Typography>
                            <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                                Have a specific idea? Tell the AI to write it immediately.
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 1 }}>
                                <TextField
                                    size="small"
                                    fullWidth
                                    placeholder="e.g. How to use AI for Literature Reviews"
                                    value={suggestedTopic}
                                    onChange={(e) => setSuggestedTopic(e.target.value)}
                                />
                                <Button
                                    variant="outlined"
                                    disabled={loading || !suggestedTopic.trim()}
                                    onClick={handleSuggest}
                                >
                                    Write
                                </Button>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>

                {/* Review Board */}
                <Grid item xs={12} md={7}>
                    <Typography variant="h6" gutterBottom>
                        Pending AI Topics
                    </Typography>
                    <Paper sx={{ mb: 4 }}>
                        <Table size="small">
                            <TableHead sx={{ bgcolor: 'rgba(0,0,0,0.05)' }}>
                                <TableRow>
                                    <TableCell>Title</TableCell>
                                    <TableCell>Source</TableCell>
                                    <TableCell align="right">Actions</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {topics.filter(t => t.status === 'pending').map((topic) => (
                                    <TableRow key={topic.id}>
                                        <TableCell sx={{ fontWeight: '500' }}>{topic.title}</TableCell>
                                        <TableCell>
                                            <Chip
                                                label={topic.source === 'ai_generated' ? 'AI' : 'Admin'}
                                                size="small"
                                                color={topic.source === 'ai_generated' ? 'secondary' : 'primary'}
                                                variant="outlined"
                                            />
                                        </TableCell>
                                        <TableCell align="right">
                                            <IconButton color="success" onClick={() => handleApprove(topic.id)}>
                                                <CheckCircleIcon />
                                            </IconButton>
                                            <IconButton color="error">
                                                <CancelIcon />
                                            </IconButton>
                                        </TableCell>
                                    </TableRow>
                                ))}
                                {topics.filter(t => t.status === 'pending').length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={3} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                                            No pending topics. Click "Generate" to start.
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </Paper>

                    <Typography variant="h6" gutterBottom>
                        Published Articles
                    </Typography>
                    <Paper>
                        <Table size="small">
                            <TableHead sx={{ bgcolor: 'rgba(0,0,0,0.05)' }}>
                                <TableRow>
                                    <TableCell>Title</TableCell>
                                    <TableCell>Date</TableCell>
                                    <TableCell align="right">View</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {posts.map((post) => (
                                    <TableRow key={post.slug}>
                                        <TableCell>{post.title}</TableCell>
                                        <TableCell>{new Date(post.published_at).toLocaleDateString()}</TableCell>
                                        <TableCell align="right">
                                            <IconButton
                                                size="small"
                                                component="a"
                                                href={`${import.meta.env.VITE_FRONTEND_URL || ''}/blog/${post.slug}`}
                                                target="_blank"
                                            >
                                                <LaunchIcon fontSize="small" />
                                            </IconButton>
                                        </TableCell>
                                    </TableRow>
                                ))}
                                {posts.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={3} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                                            No published articles yet.
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};
