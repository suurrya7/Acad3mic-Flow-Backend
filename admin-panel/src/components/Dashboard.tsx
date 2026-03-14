import { Card, CardContent, CardHeader, Grid } from '@mui/material';
import {
    PeopleOutline,
    AttachMoney,
    Assignment,
    TrendingUp,
} from '@mui/icons-material';
import { useEffect, useState } from 'react';
import { httpClient } from '../dataProvider';

interface Stats {
    total_users: number;
    paid_users: number;
    total_revenue: number;
    revenue_this_month: number;
    total_assignments: number;
    completed_assignments: number;
    active_users_24h: number;
}

const StatCard = ({ title, value, icon, color }: any) => (
    <Card>
        <CardHeader
            title={title}
            avatar={icon}
            sx={{ backgroundColor: color, color: 'white' }}
        />
        <CardContent>
            <div style={{ fontSize: '2rem', fontWeight: 'bold', textAlign: 'center' }}>
                {value}
            </div>
        </CardContent>
    </Card>
);

export const Dashboard = () => {
    const [stats, setStats] = useState<Stats | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const { data } = await httpClient.get('/admin/dashboard/stats');
                console.log('[Dashboard] Received stats:', data);
                setStats(data);
            } catch (error: any) {
                console.error('Failed to fetch stats:', error);
                setError('Failed to load dashboard statistics. Please verify backend connection.');
            }
        };

        fetchStats();
    }, []);

    if (error) return <div style={{ padding: '20px', color: 'red' }}>{error}</div>;
    if (!stats) return <div style={{ padding: '20px' }}>Loading statistics...</div>;

    return (
        <div style={{ padding: '20px' }}>
            <h1>Dashboard</h1>
            <Grid container spacing={3}>
                <Grid item xs={12} md={3}>
                    <StatCard
                        title="Total Users"
                        value={stats.total_users}
                        icon={<PeopleOutline />}
                        color="#1976d2"
                    />
                </Grid>
                <Grid item xs={12} md={3}>
                    <StatCard
                        title="Paid Users"
                        value={stats.paid_users}
                        icon={<AttachMoney />}
                        color="#388e3c"
                    />
                </Grid>
                <Grid item xs={12} md={3}>
                    <StatCard
                        title="Total Revenue"
                        value={`₹${stats.total_revenue}`}
                        icon={<TrendingUp />}
                        color="#f57c00"
                    />
                </Grid>
                <Grid item xs={12} md={3}>
                    <StatCard
                        title="Active (24h)"
                        value={stats.active_users_24h}
                        icon={<Assignment />}
                        color="#7b1fa2"
                    />
                </Grid>
            </Grid>

            <Grid container spacing={3} style={{ marginTop: '20px' }}>
                <Grid item xs={12} md={6}>
                    <Card>
                        <CardHeader title="Monthly Revenue" />
                        <CardContent>
                            <div style={{ fontSize: '1.5rem' }}>
                                ₹{stats.revenue_this_month}
                            </div>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid item xs={12} md={6}>
                    <Card>
                        <CardHeader title="Assignments" />
                        <CardContent>
                            <div>
                                Completed: {stats.completed_assignments} / {stats.total_assignments}
                            </div>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>
        </div>
    );
};
