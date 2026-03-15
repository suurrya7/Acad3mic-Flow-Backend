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
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { httpClient } from '../../dataProvider';

const ActivateButton = () => {
    const record = useRecordContext();
    const refresh = useRefresh();
    const notify = useNotify();

    const handleActivate = async (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent datagrid row click
        try {
            await httpClient.post(`/admin/prompts/${record.id}/activate`);
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
