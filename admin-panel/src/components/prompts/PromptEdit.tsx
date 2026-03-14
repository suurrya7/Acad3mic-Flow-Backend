import { Edit, useRecordContext } from 'react-admin';
import { PromptEditor } from './PromptEditor';

export const PromptEdit = () => {
    const record = useRecordContext();
    return (
        <Edit>
            <PromptEditor promptId={record?.id} />
        </Edit>
    );
};
