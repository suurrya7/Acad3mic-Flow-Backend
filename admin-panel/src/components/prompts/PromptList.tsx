import {
    List,
    Datagrid,
    TextField,
    DateField,
    BooleanField,
    NumberField,
    Button,
    useRecordContext,
    useRefresh,
    useNotify,
} from 'react-admin';
import axios from 'axios';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

const ActivateButton = () => {
    const record = useRecordContext();
    const refresh = useRefresh();
    const notify = useNotify();

    const handleActivate = async () => {
        try {
            const auth = localStorage.getItem('auth');
            const session = JSON.parse(auth || '{}');
            await axios.post(
                `${import.meta.env.VITE_API_URL}/admin/prompts/${record.id}/activate`,
                {},
                {
                    headers: { Authorization: `Bearer ${session.access_token}` },
                }
            );
            notify('Prompt activated successfully');
            refresh();
        } catch (error) {
            notify('Failed to activate prompt', { type: 'error' });
        }
    };

    if (record.is_active) {
        return <CheckCircleIcon color="success" />;
    }

    return <Button label="Activate" onClick={handleActivate} />;
};

export const PromptList = () => (
    <List>
        <Datagrid rowClick="edit">
            <NumberField source="version" />
            <BooleanField source="is_active" />
            <TextField source="notes" />
            <DateField source="created_at" showTime />
            <ActivateButton />
        </Datagrid>
    </List>
);
