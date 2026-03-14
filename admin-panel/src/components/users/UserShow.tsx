import {
    Show,
    SimpleShowLayout,
    TextField,
    EmailField,
    DateField,
    NumberField,
    BooleanField,
    Button,
    useRecordContext,
    useRefresh,
    useNotify,
} from 'react-admin';
import { Dialog, DialogTitle, DialogContent, DialogActions, TextField as MuiTextField } from '@mui/material';
import { useState } from 'react';
import axios from 'axios';

const CreditAdjustButton = () => {
    const record = useRecordContext();
    const refresh = useRefresh();
    const notify = useNotify();
    const [open, setOpen] = useState(false);
    const [amount, setAmount] = useState(0);
    const [reason, setReason] = useState('');

    const handleSubmit = async () => {
        try {
            const auth = localStorage.getItem('auth');
            const session = JSON.parse(auth || '{}');
            await axios.post(
                `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/admin/users/${record.id}/credits`,
                { amount: parseInt(amount.toString() || '0', 10), reason: reason || 'Manual Admin Adjustment' },
                {
                    headers: { Authorization: `Bearer ${session.access_token}` },
                }
            );
            notify('Credits adjusted successfully');
            setOpen(false);
            refresh();
        } catch (error) {
            notify('Failed to adjust credits', { type: 'error' });
        }
    };

    return (
        <>
            <Button label="Adjust Credits" onClick={() => setOpen(true)} />
            <Dialog open={open} onClose={() => setOpen(false)}>
                <DialogTitle>Adjust Credits</DialogTitle>
                <DialogContent>
                    <MuiTextField
                        label="Amount (+ to add, - to subtract)"
                        type="number"
                        fullWidth
                        value={amount}
                        onChange={(e) => setAmount(parseInt(e.target.value))}
                        style={{ marginBottom: 16, marginTop: 8 }}
                    />
                    <MuiTextField
                        label="Reason"
                        fullWidth
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                    />
                </DialogContent>
                <DialogActions>
                    <Button label="Cancel" onClick={() => setOpen(false)} />
                    <Button label="Submit" onClick={handleSubmit} />
                </DialogActions>
            </Dialog>
        </>
    );
};

export const UserShow = () => (
    <Show>
        <SimpleShowLayout>
            <EmailField source="email" />
            <TextField source="subscription_tier" />
            <NumberField source="word_balance" />
            <NumberField source="grading_balance" />
            <BooleanField source="is_admin" />
            <BooleanField source="is_banned" />
            <DateField source="created_at" showTime />
            <DateField source="last_reset_date" showTime />
            <CreditAdjustButton />
        </SimpleShowLayout>
    </Show>
);
